# core/finance/query_engine.py
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class TransactionDirection(Enum):
    SENT = "sent"
    RECEIVED = "received"

@dataclass
class TransactionSummary:
    """Data class for transaction summaries at any level"""
    total_amount: Decimal = Decimal('0')
    total_transactions: int = 0
    
    def add_transaction(self, amount: Decimal):
        self.total_amount += amount
        self.total_transactions += 1
    
    def to_dict(self, direction_prefix: str = "") -> Dict[str, str]:
        """Convert to dictionary with optional direction prefix"""
        if direction_prefix:
            return {
                f"Total Amount {direction_prefix}": f"{self.total_amount:.2f}",
                f"Total Transactions {direction_prefix}": str(self.total_transactions)
            }
        return {
            "Total Amount": f"{self.total_amount:.2f}",
            "Total Transactions": str(self.total_transactions)
        }

class FinancialDataQueryEngine:
    """
    Advanced query engine for financial data that creates nested,
    summarized structures for AI consumption.
    """
    
    def __init__(self):
        self.supported_services = {
            "send_money": "Money Transfer",
            "buy_airtime": "Airtime Purchase",
            "pay_bill": "Bill Payment",
            "receive_money": "Money Received"
        }
    
    def process_transactions(
        self, 
        user_name: str,
        user_id: str,
        transactions: List[Dict[str, Any]],
        time_frame: str,
        user_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process transactions into the nested summarized structure.
        
        Args:
            user_name: Name of the user
            user_id: User's ID (usually their phone number)
            transactions: List of transaction dictionaries
            time_frame: Description of time frame (e.g., "January 2024", "Last 30 days")
            user_phone: User's phone number (if different from user_id)
        
        Returns:
            Nested dictionary with summaries at each level
        """
        if not transactions:
            return self._create_empty_response(user_name, time_frame)
        
        # Normalize user identifier
        user_identifier = user_phone or user_id
        
        # Step 1: Calculate user-level summaries
        user_summary = self._calculate_user_summary(transactions, user_identifier)
        
        # Step 2: Group by counterparty (receiver/sender)
        by_counterparty = self._group_by_counterparty(transactions, user_identifier)
        
        # Step 3: Build the nested structure
        result = {
            f"User {user_name} Financial Data for {time_frame}": {
                "User Summary": user_summary,
                **self._build_counterparty_structure(by_counterparty, user_identifier)
            }
        }
        
        return result
    
    def _calculate_user_summary(
        self, 
        transactions: List[Dict], 
        user_identifier: str
    ) -> Dict[str, str]:
        """Calculate summary statistics for the user"""
        sent_summary = TransactionSummary()
        received_summary = TransactionSummary()
        
        for tx in transactions:
            amount = self._safe_decimal(tx.get('amount_paid', 0))
            direction = self._get_transaction_direction(tx, user_identifier)
            
            if direction == TransactionDirection.SENT:
                sent_summary.add_transaction(amount)
            else:
                received_summary.add_transaction(amount)
        
        return {
            "Total Amount Sent": f"{sent_summary.total_amount:.2f}",
            "Total Amount Received": f"{received_summary.total_amount:.2f}",
            "Total Transactions Sent": str(sent_summary.total_transactions),
            "Total Transactions Received": str(received_summary.total_transactions)
        }
    
    def _group_by_counterparty(
        self, 
        transactions: List[Dict], 
        user_identifier: str
    ) -> Dict[str, List[Dict]]:
        """Group transactions by counterparty (who the user transacted with)"""
        counterparty_groups = defaultdict(list)
        
        for tx in transactions:
            counterparty = self._extract_counterparty(tx, user_identifier)
            counterparty_groups[counterparty].append(tx)
        
        return dict(counterparty_groups)
    
    def _extract_counterparty(self, tx: Dict, user_identifier: str) -> str:
        """Extract the counterparty name from a transaction"""
        direction = self._get_transaction_direction(tx, user_identifier)
        
        if direction == TransactionDirection.SENT:
            # For sent transactions, counterparty is the receiver
            return (
                tx.get('beneficiary_name') or 
                tx.get('receiver_name') or 
                tx.get('receiver_phone') or 
                "Unknown Receiver"
            )
        else:
            # For received transactions, counterparty is the sender
            return (
                tx.get('sender_name') or 
                tx.get('customer_name') or 
                tx.get('sender_phone') or 
                "Unknown Sender"
            )
    
    def _build_counterparty_structure(
        self, 
        counterparty_groups: Dict[str, List[Dict]],
        user_identifier: str
    ) -> Dict[str, Any]:
        """Build the nested structure for each counterparty"""
        result = {}
        
        for counterparty, transactions in counterparty_groups.items():
            # Calculate counterparty-level summary
            counterparty_summary = self._calculate_counterparty_summary(
                transactions, user_identifier
            )
            
            # Group transactions by service within this counterparty
            by_service = self._group_by_service(transactions)
            
            # Build service structure
            service_structure = {}
            for service, service_txs in by_service.items():
                service_summary = self._calculate_service_summary(
                    service_txs, user_identifier
                )
                
                # Group by reference within service
                by_reference = self._group_by_reference(service_txs)
                
                reference_structure = {}
                for reference, ref_txs in by_reference.items():
                    reference_summary = self._calculate_reference_summary(
                        ref_txs, user_identifier
                    )
                    
                    # Add individual transactions
                    transactions_dict = {}
                    for i, tx in enumerate(ref_txs, 1):
                        tx_id = tx.get('id') or f"Transaction_{i}"
                        transactions_dict[tx_id] = self._format_transaction(
                            tx, user_identifier
                        )
                    
                    # Build reference node
                    reference_structure[f"Reference {reference}"] = {
                        "Reference Summary": reference_summary,
                        **transactions_dict
                    }
                
                # Build service node
                service_structure[f"Service {service}"] = {
                    "Service Summary": service_summary,
                    **reference_structure
                }
            
            # Build counterparty node
            result[f"Receiver {counterparty}"] = {
                "Receiver Summary": counterparty_summary,
                **service_structure
            }
        
        return result
    
    def _calculate_counterparty_summary(
        self, 
        transactions: List[Dict],
        user_identifier: str
    ) -> Dict[str, str]:
        """Calculate summary for a specific counterparty"""
        sent_summary = TransactionSummary()
        received_summary = TransactionSummary()
        
        for tx in transactions:
            amount = self._safe_decimal(tx.get('amount_paid', 0))
            direction = self._get_transaction_direction(tx, user_identifier)
            
            if direction == TransactionDirection.SENT:
                sent_summary.add_transaction(amount)
            else:
                received_summary.add_transaction(amount)
        
        return {
            "Total Amount Sent to Receiver": f"{sent_summary.total_amount:.2f}",
            "Total Amount Received from Receiver": f"{received_summary.total_amount:.2f}",
            "Total Transactions Sent to Receiver": str(sent_summary.total_transactions),
            "Total Transactions Received from Receiver": str(received_summary.total_transactions)
        }
    
    def _group_by_service(self, transactions: List[Dict]) -> Dict[str, List[Dict]]:
        """Group transactions by service type"""
        service_groups = defaultdict(list)
        
        for tx in transactions:
            intent = tx.get('intent', 'unknown')
            service = self.supported_services.get(intent, f"Unknown Service ({intent})")
            service_groups[service].append(tx)
        
        return dict(service_groups)
    
    def _calculate_service_summary(
        self, 
        transactions: List[Dict],
        user_identifier: str
    ) -> Dict[str, str]:
        """Calculate summary for a specific service"""
        sent_summary = TransactionSummary()
        received_summary = TransactionSummary()
        
        for tx in transactions:
            amount = self._safe_decimal(tx.get('amount_paid', 0))
            direction = self._get_transaction_direction(tx, user_identifier)
            
            if direction == TransactionDirection.SENT:
                sent_summary.add_transaction(amount)
            else:
                received_summary.add_transaction(amount)
        
        return {
            "Total Amount Sent for Service": f"{sent_summary.total_amount:.2f}",
            "Total Amount Received for Service": f"{received_summary.total_amount:.2f}",
            "Total Transactions Sent for Service": str(sent_summary.total_transactions),
            "Total Transactions Received for Service": str(received_summary.total_transactions)
        }
    
    def _group_by_reference(self, transactions: List[Dict]) -> Dict[str, List[Dict]]:
        """Group transactions by reference/purpose"""
        reference_groups = defaultdict(list)
        
        for tx in transactions:
            reference = tx.get('reference') or tx.get('description') or "No Reference"
            reference_groups[reference].append(tx)
        
        return dict(reference_groups)
    
    def _calculate_reference_summary(
        self, 
        transactions: List[Dict],
        user_identifier: str
    ) -> Dict[str, str]:
        """Calculate summary for a specific reference"""
        sent_summary = TransactionSummary()
        received_summary = TransactionSummary()
        
        for tx in transactions:
            amount = self._safe_decimal(tx.get('amount_paid', 0))
            direction = self._get_transaction_direction(tx, user_identifier)
            
            if direction == TransactionDirection.SENT:
                sent_summary.add_transaction(amount)
            else:
                received_summary.add_transaction(amount)
        
        return {
            "Total Amount Sent for Reference": f"{sent_summary.total_amount:.2f}",
            "Total Amount Received for Reference": f"{received_summary.total_amount:.2f}",
            "Total Transactions Sent for Reference": str(sent_summary.total_transactions),
            "Total Transactions Received for Reference": str(received_summary.total_transactions)
        }
    
    def _format_transaction(self, tx: Dict, user_identifier: str) -> Dict[str, str]:
        """Format a single transaction for output"""
        amount = self._safe_decimal(tx.get('amount_paid', 0))
        
        return {
            "Amount": f"{amount:.2f}",
            "Currency": tx.get('currency', 'GHS'),
            "senderPhone": tx.get('sender_phone', user_identifier),
            "receiverPhone": tx.get('receiver_phone', tx.get('recipient', '')),
            "network": tx.get('network', 'MTN'),
            "paymentMethod": tx.get('payment_method', 'MOBILE_MONEY'),
            "customerName": tx.get('customer_name', ''),
            "senderName": tx.get('sender_name', ''),
            "receiverName": tx.get('receiver_name', ''),
            "senderProvider": tx.get('sender_provider', ''),
            "receiverProvider": tx.get('receiver_provider', ''),
            "serviceName": tx.get('service_name', self._infer_service_name(tx)),
            "reference": tx.get('reference', ''),
            "beneficiaryId": tx.get('beneficiaryId', ''),
            "beneficiaryName": tx.get('beneficiary_name', ''),
            "amountPaid": f"{amount:.2f}",
            "date": tx.get('date_paid', tx.get('created_at', '')),
            "status": tx.get('status', 'SUCCESS')
        }
    
    def _get_transaction_direction(
        self, 
        tx: Dict, 
        user_identifier: str
    ) -> TransactionDirection:
        """Determine if transaction was sent or received by user"""
        sender = tx.get('senderPhone', '')
        receiver = tx.get('receiverPhone', tx.get('recipient', ''))
        
        if sender == user_identifier:
            return TransactionDirection.SENT
        elif receiver == user_identifier:
            return TransactionDirection.RECEIVED
        else:
            # If can't determine, check intent
            intent = tx.get('intent', '')
            if intent in ['send_money', 'buy_airtime', 'pay_bill']:
                return TransactionDirection.SENT
            return TransactionDirection.RECEIVED
    
    def _safe_decimal(self, value: Any) -> Decimal:
        """Safely convert any value to Decimal"""
        try:
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))
        except:
            return Decimal('0')
    
    def _infer_service_name(self, tx: Dict) -> str:
        """Infer service name from transaction data"""
        intent = tx.get('intent', '')
        if intent == 'send_money':
            return f"Money Transfer to {tx.get('recipient', 'Unknown')}"
        elif intent == 'buy_airtime':
            return f"Airtime Purchase for {tx.get('phone_number', 'Unknown')}"
        elif intent == 'pay_bill':
            return f"Bill Payment to {tx.get('account_number', 'Unknown')}"
        return "Financial Transaction"
    
    def _create_empty_response(self, user_name: str, time_frame: str) -> Dict[str, Any]:
        """Create empty response structure when no transactions exist"""
        return {
            f"User {user_name} Financial Data for {time_frame}": {
                "User Summary": {
                    "Total Amount Sent": "0.00",
                    "Total Amount Received": "0.00",
                    "Total Transactions Sent": "0",
                    "Total Transactions Received": "0"
                }
            }
        }


# Enhanced UserRAGManager with the new query engine
class EnhancedUserRAGManager:
    """Enhanced RAG manager using the financial query engine"""
    
    def __init__(self):
        self.query_engine = FinancialDataQueryEngine()
    
    def get_financial_insights_context(
        self,
        user_name: str,
        user_id: str,
        transactions: List[Dict],
        time_frame: str,
        user_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get financial insights context using the query engine.
        This replaces the old _get_transaction_history method.
        """
        return self.query_engine.process_transactions(
            user_name=user_name,
            user_id=user_id,
            transactions=transactions,
            time_frame=time_frame,
            user_phone=user_phone
        )


# Example usage and testing
def test_query_engine():
    """Test function to demonstrate the query engine"""
    
    # Sample transaction data
    sample_transactions = [
        {
            'id': 'tx1',
            'intent': 'send_money',
            'amountPaid': 50.00,
            'senderPhone': '233501234567',
            'recipient': '233247654321',
            'beneficiaryName': 'John Doe',
            'reference': 'Food',
            'date_paid': '2024-01-15T10:30:00'
        },
        {
            'id': 'tx2',
            'intent': 'send_money',
            'amountPaid': 30.00,
            'senderPhone': '233501234567',
            'recipient': '233247654321',
            'beneficiaryName': 'John Doe',
            'reference': 'Transport',
            'date_paid': '2024-01-20T14:20:00'
        },
        {
            'id': 'tx3',
            'intent': 'buy_airtime',
            'amountPaid': 10.00,
            'senderPhone': '233501234567',
            'phone_number': '233247654321',
            'beneficiaryName': 'John Doe',
            'reference': 'Airtime',
            'network': 'MTN',
            'date_paid': '2024-01-25T09:15:00'
        },
        {
            'id': 'tx4',
            'intent': 'receive_money',
            'amountPaid': 100.00,
            'senderPhone': '233987654321',
            'receiverPhone': '233501234567',
            'senderName': 'Alice Smith',
            'reference': 'Payment',
            'date_paid': '2024-01-28T16:45:00'
        }
    ]
    
    # Initialize engine
    engine = FinancialDataQueryEngine()
    
    # Process transactions
    result = engine.process_transactions(
        user_name="Kwame",
        user_id="233501234567",
        transactions=sample_transactions,
        time_frame="January 2024"
    )
    
    # Pretty print the result
    import json
    print(json.dumps(result, indent=2, default=str))
    
    return result


if __name__ == "__main__":
    test_query_engine()