"""Machine Learning-based spam classifier using scikit-learn."""
import os
import pickle
import re
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from app.logger import setup_logger

logger = setup_logger(__name__)


class MLSpamClassifier:
    """Machine Learning-based spam classifier."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize ML spam classifier.
        
        Args:
            model_path: Path to saved model file (optional)
        """
        self.model_path = model_path or "models/spam_classifier.pkl"
        self.model: Optional[Pipeline] = None
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.is_trained = False
        
        # Load model if it exists
        self._load_model()
    
    def _load_model(self) -> None:
        """Load trained model from disk if it exists."""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                self.is_trained = True
                logger.info(f"Loaded ML spam classifier from {self.model_path}")
            else:
                logger.info("No trained ML model found. Using rule-based classifier only.")
        except Exception as e:
            logger.warning(f"Failed to load ML model: {e}. Using rule-based classifier only.")
            self.model = None
            self.is_trained = False
    
    def _save_model(self) -> None:
        """Save trained model to disk."""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            logger.info(f"Saved ML spam classifier to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to save ML model: {e}", exc_info=True)
    
    def _extract_features(self, parsed_email: Dict[str, Any]) -> str:
        """
        Extract text features from email for ML model.
        
        Args:
            parsed_email: Parsed email dictionary
        
        Returns:
            Combined text string for classification
        """
        subject = parsed_email.get("subject", "")
        body_text = parsed_email.get("body_text", "")
        body_html = parsed_email.get("body_html", "")
        from_email = parsed_email.get("from_email", "")
        
        # Remove HTML tags from HTML body
        if body_html:
            body_html = re.sub(r'<[^>]+>', ' ', body_html)
            body_html = re.sub(r'\s+', ' ', body_html).strip()
        
        # Combine all text
        text_parts = [
            f"FROM:{from_email}",
            f"SUBJECT:{subject}",
            body_text or "",
            body_html or "",
        ]
        
        return " ".join(text_parts).lower()
    
    def predict(self, parsed_email: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict if email is spam using ML model.
        
        Args:
            parsed_email: Parsed email dictionary
        
        Returns:
            {
                'is_spam': bool,
                'is_promotion': bool,
                'confidence': float,
                'ml_score': float,
                'method': str ('ml' or 'none')
            }
        """
        if not self.is_trained or self.model is None:
            return {
                'is_spam': False,
                'is_promotion': False,
                'confidence': 0.0,
                'ml_score': 0.0,
                'method': 'none'
            }
        
        try:
            # Extract features
            text = self._extract_features(parsed_email)
            
            # Predict
            prediction = self.model.predict([text])[0]
            probabilities = self.model.predict_proba([text])[0]
            
            # Map prediction: 0 = ham, 1 = spam, 2 = promotion
            # For binary classification: 0 = ham, 1 = spam
            if len(probabilities) == 2:
                # Binary: ham vs spam
                spam_prob = probabilities[1]
                is_spam = prediction == 1
                is_promotion = False
            else:
                # Multi-class: ham, spam, promotion
                spam_prob = probabilities[1] if len(probabilities) > 1 else 0.0
                promo_prob = probabilities[2] if len(probabilities) > 2 else 0.0
                is_spam = prediction == 1
                is_promotion = prediction == 2
            
            confidence = max(probabilities) if len(probabilities) > 0 else 0.0
            
            return {
                'is_spam': is_spam,
                'is_promotion': is_promotion,
                'confidence': float(confidence),
                'ml_score': float(spam_prob),
                'method': 'ml'
            }
        except Exception as e:
            logger.error(f"ML prediction error: {e}", exc_info=True)
            return {
                'is_spam': False,
                'is_promotion': False,
                'confidence': 0.0,
                'ml_score': 0.0,
                'method': 'error'
            }
    
    def train(
        self,
        emails: List[Dict[str, Any]],
        labels: List[str],
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Dict[str, Any]:
        """
        Train the ML model on email data.
        
        Args:
            emails: List of parsed email dictionaries
            labels: List of labels ('ham', 'spam', 'promotion')
            test_size: Fraction of data to use for testing
            random_state: Random seed for reproducibility
        
        Returns:
            Training metrics dictionary
        """
        try:
            # Extract features
            texts = [self._extract_features(email) for email in emails]
            
            # Convert labels to numeric
            label_map = {'ham': 0, 'spam': 1, 'promotion': 2}
            y = np.array([label_map.get(label.lower(), 0) for label in labels])
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                texts, y, test_size=test_size, random_state=random_state, stratify=y
            )
            
            # Create pipeline
            self.model = Pipeline([
                ('tfidf', TfidfVectorizer(
                    max_features=10000,
                    ngram_range=(1, 2),
                    stop_words='english',
                    min_df=2,
                    max_df=0.95
                )),
                ('classifier', MultinomialNB(alpha=1.0))
            ])
            
            # Train
            self.model.fit(X_train, y_train)
            
            # Evaluate
            train_score = self.model.score(X_train, y_train)
            test_score = self.model.score(X_test, y_test)
            
            # Predictions for detailed metrics
            y_pred = self.model.predict(X_test)
            
            # Calculate per-class accuracy
            metrics = {
                'train_accuracy': float(train_score),
                'test_accuracy': float(test_score),
                'train_size': len(X_train),
                'test_size': len(X_test),
            }
            
            # Per-class metrics
            for label_name, label_num in label_map.items():
                mask = y_test == label_num
                if mask.sum() > 0:
                    class_accuracy = (y_pred[mask] == y_test[mask]).mean()
                    metrics[f'{label_name}_accuracy'] = float(class_accuracy)
                    metrics[f'{label_name}_count'] = int(mask.sum())
            
            self.is_trained = True
            self._save_model()
            
            logger.info(f"ML model trained successfully. Test accuracy: {test_score:.4f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Training error: {e}", exc_info=True)
            raise


# Global ML classifier instance
ml_spam_classifier = MLSpamClassifier()

