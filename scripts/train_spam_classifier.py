#!/usr/bin/env python3
"""
Train ML spam classifier on email dataset.

Usage:
    python scripts/train_spam_classifier.py --dataset path/to/dataset.csv
    python scripts/train_spam_classifier.py --use-sample  # Use sample dataset
"""

import sys
import os
import argparse
import csv
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml_spam_classifier import MLSpamClassifier
from app.email_service import email_service
from app.logger import setup_logger

logger = setup_logger(__name__)


def load_sample_dataset():
    """
    Load a sample dataset for training.
    This is a basic dataset - in production, use a larger, real dataset.
    """
    # Sample spam emails
    spam_samples = [
        {
            "subject": "Congratulations! You Won $1000",
            "body_text": "Click here to claim your prize! Limited time offer. Act now!",
            "from_email": "winner@lottery.com",
            "body_html": "",
        },
        {
            "subject": "Free Viagra Pills",
            "body_text": "Buy cheap medication online. No prescription needed.",
            "from_email": "pharmacy@spam.com",
            "body_html": "",
        },
        {
            "subject": "URGENT: Claim Your Inheritance",
            "body_text": "Nigerian prince needs your help. Send money to claim inheritance.",
            "from_email": "prince@nigeria.com",
            "body_html": "",
        },
        {
            "subject": "Work From Home - Make $5000/week",
            "body_text": "Earn money from home. No experience needed. Click here now!",
            "from_email": "jobs@spam.com",
            "body_html": "",
        },
        {
            "subject": "You Won the Lottery!",
            "body_text": "Congratulations! You are a winner. Claim your prize now!",
            "from_email": "lottery@spam.com",
            "body_html": "",
        },
    ]
    
    # Sample promotion emails
    promo_samples = [
        {
            "subject": "Special Sale - 50% Off Everything",
            "body_text": "Don't miss our exclusive deal! Use code SAVE50. Unsubscribe here.",
            "from_email": "marketing@store.com",
            "body_html": "<p>Special offer! <a href='unsubscribe'>Unsubscribe</a></p>",
        },
        {
            "subject": "Newsletter: Weekly Deals",
            "body_text": "Check out our weekly deals and promotions. Manage preferences.",
            "from_email": "newsletter@company.com",
            "body_html": "",
        },
        {
            "subject": "Limited Time Offer - Free Shipping",
            "body_text": "Get free shipping on all orders. Shop now! Unsubscribe.",
            "from_email": "promo@shop.com",
            "body_html": "",
        },
    ]
    
    # Sample legitimate emails
    ham_samples = [
        {
            "subject": "Need help with my account",
            "body_text": "I'm having trouble logging in. Can you help me reset my password?",
            "from_email": "customer@example.com",
            "body_html": "",
        },
        {
            "subject": "Question about your service",
            "body_text": "Hi, I have a question about how to use your product. Can someone help?",
            "from_email": "user@example.com",
            "body_html": "",
        },
        {
            "subject": "Bug Report",
            "body_text": "I found a bug in the application. Here are the details...",
            "from_email": "developer@example.com",
            "body_html": "",
        },
        {
            "subject": "Feature Request",
            "body_text": "I would like to request a new feature. Is this possible?",
            "from_email": "user@example.com",
            "body_html": "",
        },
    ]
    
    emails = spam_samples + promo_samples + ham_samples
    labels = ['spam'] * len(spam_samples) + ['promotion'] * len(promo_samples) + ['ham'] * len(ham_samples)
    
    return emails, labels


def load_csv_dataset(filepath: str):
    """Load dataset from CSV file."""
    emails = []
    labels = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            emails.append({
                "subject": row.get("subject", ""),
                "body_text": row.get("body_text", ""),
                "body_html": row.get("body_html", ""),
                "from_email": row.get("from_email", ""),
            })
            labels.append(row.get("label", "ham").lower())
    
    return emails, labels


def main():
    parser = argparse.ArgumentParser(description="Train ML spam classifier")
    parser.add_argument(
        "--dataset",
        type=str,
        help="Path to CSV dataset file (columns: subject, body_text, body_html, from_email, label)"
    )
    parser.add_argument(
        "--use-sample",
        action="store_true",
        help="Use built-in sample dataset for training"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="models/spam_classifier.pkl",
        help="Path to save trained model"
    )
    
    args = parser.parse_args()
    
    # Load dataset
    if args.use_sample:
        logger.info("Using sample dataset")
        emails, labels = load_sample_dataset()
    elif args.dataset:
        logger.info(f"Loading dataset from {args.dataset}")
        emails, labels = load_csv_dataset(args.dataset)
    else:
        logger.error("Please provide --dataset or --use-sample")
        return 1
    
    logger.info(f"Loaded {len(emails)} emails")
    logger.info(f"Labels: {dict(zip(*zip(*[(l, labels.count(l)) for l in set(labels)])))}")
    
    # Initialize classifier
    classifier = MLSpamClassifier(model_path=args.model_path)
    
    # Train
    logger.info("Training model...")
    try:
        metrics = classifier.train(emails, labels)
        
        logger.info("Training completed!")
        logger.info(f"Train accuracy: {metrics['train_accuracy']:.4f}")
        logger.info(f"Test accuracy: {metrics['test_accuracy']:.4f}")
        
        if 'spam_accuracy' in metrics:
            logger.info(f"Spam accuracy: {metrics['spam_accuracy']:.4f}")
        if 'promotion_accuracy' in metrics:
            logger.info(f"Promotion accuracy: {metrics['promotion_accuracy']:.4f}")
        if 'ham_accuracy' in metrics:
            logger.info(f"Ham accuracy: {metrics['ham_accuracy']:.4f}")
        
        logger.info(f"Model saved to {args.model_path}")
        return 0
        
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

