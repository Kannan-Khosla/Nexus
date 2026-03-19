"""Spam classification service for filtering unwanted emails."""
from typing import Dict, Any, List, Optional
import re
from app.logger import setup_logger
from app.config import settings

logger = setup_logger(__name__)

# Try to import ML classifier (optional)
try:
    from app.ml_spam_classifier import ml_spam_classifier
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML spam classifier not available. Using rule-based only.")


class SpamClassifier:
    """Classifies emails as spam/ham and filters promotions/ads."""
    
    def __init__(self):
        # Spam keywords and patterns
        self.spam_keywords = [
            # Common spam words
            'unsubscribe', 'click here', 'limited time', 'act now', 'urgent action',
            'winner', 'congratulations', 'free money', 'claim your prize', 'you won',
            'viagra', 'cialis', 'pharmacy', 'pills', 'medication',
            'nigerian prince', 'inheritance', 'lottery', 'sweepstakes',
            'debt relief', 'consolidate debt', 'credit repair',
            'work from home', 'make money', 'get rich', 'earn $',
            'meet singles', 'dating', 'find love',
            'enlarge', 'weight loss', 'lose weight fast',
            'rolex', 'replica', 'cheap watches',
            'bitcoin', 'cryptocurrency investment', 'crypto trading',
            'loan approval', 'pre-approved', 'guaranteed approval',
        ]
        
        # Promotion/ad keywords
        self.promotion_keywords = [
            'promotion', 'special offer', 'limited offer', 'exclusive deal',
            'discount', 'sale', 'clearance', 'save up to', 'percent off',
            'coupon', 'voucher', 'promo code', 'use code',
            'subscribe', 'newsletter', 'marketing', 'advertisement',
            'sponsored', 'ad', 'commercial', 'promotional',
            'unsubscribe from', 'manage preferences', 'email preferences',
            'view in browser', 'view online', 'web version',
            'this email was sent to', 'you are receiving this',
            'update your preferences', 'change email settings',
        ]
        
        # Spam subject patterns
        self.spam_subject_patterns = [
            r'\b(?:free|win|winner|prize|congratulations|urgent|act now)\b',
            r'\b(?:viagra|cialis|pills|medication|pharmacy)\b',
            r'\b(?:click here|click now|visit now)\b',
            r'\$\d+',  # Money amounts
            r'\d+% (?:off|discount|sale)',
            r'(?:re:?|fwd?:?)\s*(?:fwd?:?|re:?)\s*(?:fwd?:?|re:?)',  # Multiple forwards/replies
        ]
        
        # Promotion subject patterns
        self.promotion_subject_patterns = [
            r'\b(?:sale|discount|offer|deal|promotion|clearance)\b',
            r'\d+% (?:off|discount)',
            r'free shipping',
            r'limited time',
            r'buy now',
        ]
        
        # Suspicious sender patterns
        self.suspicious_sender_patterns = [
            r'^[a-z0-9._%+-]+@(?:noreply|no-reply|donotreply|do-not-reply|mailer|marketing|promo|sales|offers|deals)',
            r'@(?:mail|email|send|promo|deal|offer|sale|discount|marketing|ad|advert)\.',
        ]
        
        # List-Unsubscribe header indicates marketing/promotional emails
        self.has_list_unsubscribe = False
    
    def classify(self, parsed_email: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify an email as spam, promotion, or ham (legitimate).
        Uses both rule-based and ML-based classification for better accuracy.
        
        Returns:
            {
                'is_spam': bool,
                'is_promotion': bool,
                'is_ham': bool,
                'confidence': float (0.0-1.0),
                'reasons': List[str],
                'category': str ('spam', 'promotion', 'ham'),
                'spam_score': float,
                'promotion_score': float,
                'ml_used': bool,
                'ml_confidence': float
            }
        """
        # Get ML prediction if available and enabled
        ml_prediction = None
        ml_used = False
        if ML_AVAILABLE and settings.email_ml_classifier_enabled:
            try:
                ml_prediction = ml_spam_classifier.predict(parsed_email)
                ml_used = ml_prediction.get('method') == 'ml'
            except Exception as e:
                logger.warning(f"ML prediction failed: {e}")
        
        subject = parsed_email.get("subject", "").lower()
        from_email = parsed_email.get("from_email", "").lower()
        body_text = parsed_email.get("body_text", "").lower()
        body_html = parsed_email.get("body_html", "").lower()
        
        # Combine all text for analysis
        full_text = f"{subject} {body_text} {body_html}".lower()
        
        reasons = []
        spam_score = 0.0
        promotion_score = 0.0
        
        # Check for List-Unsubscribe header (indicates marketing/promotional)
        headers = parsed_email.get("_headers", {})
        if headers.get("List-Unsubscribe") or headers.get("List-Unsubscribe-Post"):
            promotion_score += 0.3
            reasons.append("Has List-Unsubscribe header (marketing email)")
        
        # Check spam keywords in subject
        spam_matches_subject = sum(1 for keyword in self.spam_keywords if keyword in subject)
        if spam_matches_subject > 0:
            spam_score += 0.4
            reasons.append(f"Spam keywords in subject ({spam_matches_subject} matches)")
        
        # Check spam keywords in body
        spam_matches_body = sum(1 for keyword in self.spam_keywords if keyword in full_text)
        if spam_matches_body > 2:
            spam_score += 0.3
            reasons.append(f"Multiple spam keywords in body ({spam_matches_body} matches)")
        
        # Check spam subject patterns
        for pattern in self.spam_subject_patterns:
            if re.search(pattern, subject, re.IGNORECASE):
                spam_score += 0.2
                reasons.append(f"Spam pattern in subject: {pattern}")
                break
        
        # Check promotion keywords
        promotion_matches_subject = sum(1 for keyword in self.promotion_keywords if keyword in subject)
        if promotion_matches_subject > 0:
            promotion_score += 0.3
            reasons.append(f"Promotion keywords in subject ({promotion_matches_subject} matches)")
        
        promotion_matches_body = sum(1 for keyword in self.promotion_keywords if keyword in full_text)
        if promotion_matches_body > 3:
            promotion_score += 0.4
            reasons.append(f"Multiple promotion keywords in body ({promotion_matches_body} matches)")
        
        # Check promotion subject patterns
        for pattern in self.promotion_subject_patterns:
            if re.search(pattern, subject, re.IGNORECASE):
                promotion_score += 0.2
                reasons.append(f"Promotion pattern in subject: {pattern}")
                break
        
        # Check suspicious sender patterns
        for pattern in self.suspicious_sender_patterns:
            if re.search(pattern, from_email, re.IGNORECASE):
                spam_score += 0.2
                promotion_score += 0.1
                reasons.append(f"Suspicious sender pattern: {pattern}")
                break
        
        # Check for excessive links (spam indicator)
        link_count = len(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', full_text))
        if link_count > 5:
            spam_score += 0.15
            reasons.append(f"Excessive links ({link_count} links)")
        
        # Check for unsubscribe links (promotion indicator)
        unsubscribe_count = len(re.findall(r'unsubscribe', full_text, re.IGNORECASE))
        if unsubscribe_count > 0:
            promotion_score += 0.2
            reasons.append("Contains unsubscribe link")
        
        # Check for very short body (spam indicator)
        if len(body_text.strip()) < 50 and not parsed_email.get("in_reply_to"):
            spam_score += 0.1
            reasons.append("Very short email body")
        
        # Check for all caps subject (spam indicator)
        if subject and subject.isupper() and len(subject) > 10:
            spam_score += 0.15
            reasons.append("Subject in all caps")
        
        # Normalize scores
        spam_score = min(spam_score, 1.0)
        promotion_score = min(promotion_score, 1.0)
        
        # Combine with ML prediction if available
        if ml_used and ml_prediction:
            ml_spam = ml_prediction.get('is_spam', False)
            ml_promo = ml_prediction.get('is_promotion', False)
            ml_confidence = ml_prediction.get('confidence', 0.0)
            ml_score = ml_prediction.get('ml_score', 0.0)
            
            # Weighted combination: 60% ML, 40% rule-based
            ml_weight = 0.6
            rule_weight = 0.4
            
            # Combine spam scores
            combined_spam_score = (ml_weight * ml_score) + (rule_weight * spam_score)
            
            # Combine promotion scores (ML doesn't always predict promotions separately)
            if ml_promo:
                promotion_score = max(promotion_score, ml_confidence)
            
            # Update spam_score with combined score
            spam_score = combined_spam_score
            
            reasons.append(f"ML prediction: {ml_prediction.get('method', 'unknown')} (confidence: {ml_confidence:.2f})")
            
            # Use ML prediction if confidence is high
            if ml_confidence > 0.7:
                if ml_spam:
                    spam_score = max(spam_score, 0.7)
                elif ml_promo:
                    promotion_score = max(promotion_score, 0.7)
        else:
            ml_confidence = 0.0
        
        # Determine category
        is_spam = spam_score >= 0.5
        is_promotion = promotion_score >= 0.5 and not is_spam
        
        # If it's a reply to an existing ticket, it's likely legitimate
        if parsed_email.get("in_reply_to"):
            is_spam = False
            is_promotion = False
            reasons.append("Reply to existing ticket (legitimate)")
        
        # If sender is a registered user, reduce spam score
        # (This will be checked in the calling code)
        
        category = "spam" if is_spam else ("promotion" if is_promotion else "ham")
        confidence = max(spam_score, promotion_score) if (is_spam or is_promotion) else (1.0 - max(spam_score, promotion_score))
        
        # Use ML confidence if available and higher
        if ml_used and ml_confidence > confidence:
            confidence = ml_confidence
        
        return {
            "is_spam": is_spam,
            "is_promotion": is_promotion,
            "is_ham": not is_spam and not is_promotion,
            "confidence": confidence,
            "reasons": reasons,
            "category": category,
            "spam_score": spam_score,
            "promotion_score": promotion_score,
            "ml_used": ml_used,
            "ml_confidence": ml_confidence if ml_used else 0.0,
        }
    
    def should_filter(self, parsed_email: Dict[str, Any], filter_promotions: bool = True) -> bool:
        """
        Determine if an email should be filtered (not create a ticket).
        
        Args:
            parsed_email: Parsed email dictionary
            filter_promotions: Whether to filter promotions (default: True)
        
        Returns:
            True if email should be filtered, False otherwise
        """
        classification = self.classify(parsed_email)
        
        # Always filter spam
        if classification["is_spam"]:
            logger.info(f"Filtering spam email from {parsed_email.get('from_email')}: {classification['reasons']}")
            return True
        
        # Filter promotions if enabled
        if filter_promotions and classification["is_promotion"]:
            logger.info(f"Filtering promotion email from {parsed_email.get('from_email')}: {classification['reasons']}")
            return True
        
        return False


# Global spam classifier instance
spam_classifier = SpamClassifier()

