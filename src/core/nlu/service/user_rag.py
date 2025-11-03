# core/rag/user_data_manager.py
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from collections import defaultdict
from sqlalchemy.orm import Session
from src.core.histories.model.history import History
from utilities.dbconfig import SessionLocal

class UserRAGManager:
    """Manages user data for RAG augmentation using transaction history"""
    
    def __init__(self, max_context_tokens: int = 4000):
        self.max_context_tokens = max_context_tokens
        self.estimated_token_ratio = 4  # chars per token estimate
    
    def get_optimized_user_context(
        self, 
        user_id: str, 
        intent: str,
        current_slots: Dict,
        full_user_data: Dict
    ) -> Dict[str, Any]:
        """
        Get optimized user context based on intent and transaction history
        """
        # Extract core user bio (always included)
        core_bio = self._extract_core_bio(full_user_data)
        
        # Get transaction history from database
        transaction_data = self._get_transaction_history(user_id, intent, current_slots)
        
        # Compress and summarize transaction data
        compressed_data = self._compress_transaction_data(
            transaction_data, intent, current_slots
        )
        
        # Calculate token usage and optimize
        optimized_context = self._optimize_context_size(
            core_bio, compressed_data, intent
        )
        
        return optimized_context
    
    def _extract_core_bio(self, user_data: Dict) -> Dict:
        """Extract essential user bio information"""
        return {
            "user_id": user_data.get("user_id"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "is_active": user_data.get("is_active"),
            "member_since": user_data.get("created_at"),
            "location": "Ghana"  # Default location
        }
    
    def _get_transaction_history(self, user_id: str, intent: str, slots: Dict) -> List[Dict]:
        """Fetch transaction history from database"""
        try:
            db = SessionLocal()
            
            # Base query for user's transactions
            query = db.query(History).filter(History.user_id == user_id)
            
            # Apply time filters based on intent
            days_to_look_back = self._get_lookback_period(intent)
            start_date = datetime.utcnow() - timedelta(days=days_to_look_back)
            query = query.filter(History.created_at >= start_date)
            
            # Apply intent-specific filters
            if intent in ["budgeting_advice", "financial_tips", "expense_report"]:
                # Focus on debit transactions for spending analysis
                query = query.filter(History.transaction_type == 'debit')
            elif intent == "savings_tips":
                # Include both debit and credit for savings pattern analysis
                pass
            elif intent in ["send_money", "buy_airtime", "pay_bill"]:
                # Focus on specific transaction types
                query = query.filter(History.intent == intent)
            
            # Order by most recent and limit
            transactions = query.order_by(History.created_at.desc()).limit(100).all()
            
            # Convert to dictionary format
            transaction_list = []
            for tx in transactions:
                transaction_list.append({
                    "id": str(tx.id),
                    "intent": tx.intent,
                    "transaction_type": tx.transaction_type,
                    "amount": float(tx.amount) if tx.amount else 0.0,
                    "recipient": tx.recipient,
                    "phone_number": tx.phone_number,
                    "category": tx.category,
                    "status": tx.status,
                    "description": tx.description,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                    "metadata": tx.transaction_metadata or {}
                })
            
            return transaction_list
            
        except Exception as e:
            print(f"Error fetching transaction history: {e}")
            return []
        finally:
            db.close()
    
    def _get_lookback_period(self, intent: str) -> int:
        """Determine how far back to look in transaction history based on intent"""
        lookback_map = {
            "budgeting_advice": 90,  # 3 months for budgeting patterns
            "savings_tips": 180,     # 6 months for savings trends
            "investment_advice": 365, # 1 year for investment history
            "debt_management": 180,   # 6 months for debt patterns
            "send_money": 60,         # 2 months for transfer patterns
            "buy_airtime": 30,        # 1 month for airtime usage
            "pay_bill": 90,           # 3 months for bill payments
            "financial_tips": 60,     # 2 months for general tips
            "expense_report": 30,     # 1 month for current expenses
            "default": 30             # 1 month default
        }
        return lookback_map.get(intent, lookback_map["default"])
    
    def _compress_transaction_data(self, transactions: List[Dict], intent: str, slots: Dict) -> Dict:
        """Compress transaction data based on intent"""
        if not transactions:
            return {"no_data": True, "message": "No transaction history available"}
        
        compression_strategies = {
            "budgeting_advice": self._compress_for_budgeting,
            "savings_tips": self._compress_for_savings,
            "investment_advice": self._compress_for_investment,
            "debt_management": self._compress_for_debt,
            "send_money": self._compress_for_money_transfer,
            "buy_airtime": self._compress_for_airtime,
            "pay_bill": self._compress_for_bills,
            "financial_tips": self._compress_for_financial_tips,
            "expense_report": self._compress_for_expense_report,
            "default": self._compress_general_transactions
        }
        
        compressor = compression_strategies.get(intent, compression_strategies["default"])
        return compressor(transactions, slots)
    
    def _compress_for_budgeting(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Compress transactions for budgeting advice"""
        debit_transactions = [t for t in transactions if t.get("transaction_type") == "debit"]
        
        # Calculate spending by category
        category_spending = defaultdict(float)
        for tx in debit_transactions:
            category = tx.get("category", "uncategorized")
            amount = tx.get("amount", 0)
            category_spending[category] += amount
        
        # Calculate monthly averages
        if debit_transactions:
            first_date = min(datetime.fromisoformat(tx["created_at"].replace('Z', '+00:00')) 
                           for tx in debit_transactions if tx.get("created_at"))
            days_span = (datetime.now() - first_date).days or 1
            monthly_avg = sum(tx.get("amount", 0) for tx in debit_transactions) / (days_span / 30)
        else:
            monthly_avg = 0
        
        return {
            "total_spent": sum(tx.get("amount", 0) for tx in debit_transactions),
            "monthly_average": monthly_avg,
            "top_spending_categories": dict(sorted(category_spending.items(), 
                                                 key=lambda x: x[1], reverse=True)[:5]),
            "transaction_count": len(debit_transactions),
            "key_insights": self._generate_budgeting_insights(category_spending, monthly_avg)
        }
    
    def _compress_for_savings(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Compress transactions for savings tips"""
        debit_transactions = [t for t in transactions if t.get("transaction_type") == "debit"]
        credit_transactions = [t for t in transactions if t.get("transaction_type") == "credit"]
        
        total_debits = sum(tx.get("amount", 0) for tx in debit_transactions)
        total_credits = sum(tx.get("amount", 0) for tx in credit_transactions)
        
        # Calculate savings rate (simplified)
        savings_rate = ((total_credits - total_debits) / total_credits * 100) if total_credits > 0 else 0
        
        return {
            "total_income": total_credits,
            "total_expenses": total_debits,
            "net_savings": total_credits - total_debits,
            "savings_rate": savings_rate,
            "key_insights": self._generate_savings_insights(total_credits, total_debits, savings_rate)
        }
    
    def _compress_for_money_transfer(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Compress transactions for money transfer patterns"""
        send_transactions = [t for t in transactions if t.get("intent") == "send_money"]
        
        # Analyze recipient patterns
        recipient_stats = defaultdict(lambda: {"count": 0, "total_amount": 0})
        for tx in send_transactions:
            recipient = tx.get("recipient", "unknown")
            recipient_stats[recipient]["count"] += 1
            recipient_stats[recipient]["total_amount"] += tx.get("amount", 0)
        
        return {
            "total_transfers": len(send_transactions),
            "total_amount_sent": sum(tx.get("amount", 0) for tx in send_transactions),
            "frequent_recipients": {
                recipient: stats 
                for recipient, stats in sorted(
                    recipient_stats.items(), 
                    key=lambda x: x[1]["count"], 
                    reverse=True
                )[:5]
            },
            "average_transfer_amount": (
                sum(tx.get("amount", 0) for tx in send_transactions) / len(send_transactions) 
                if send_transactions else 0
            )
        }
    
    def _compress_for_airtime(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Compress transactions for airtime usage patterns"""
        airtime_transactions = [t for t in transactions if t.get("intent") == "buy_airtime"]
        
        # Analyze by network/phone number
        network_stats = defaultdict(lambda: {"count": 0, "total_amount": 0})
        for tx in airtime_transactions:
            network = tx.get("phone_number", "unknown")[:6]  # Use phone prefix as network indicator
            network_stats[network]["count"] += 1
            network_stats[network]["total_amount"] += tx.get("amount", 0)
        
        return {
            "total_topups": len(airtime_transactions),
            "total_amount_spent": sum(tx.get("amount", 0) for tx in airtime_transactions),
            "usage_patterns": dict(network_stats),
            "average_topup_amount": (
                sum(tx.get("amount", 0) for tx in airtime_transactions) / len(airtime_transactions) 
                if airtime_transactions else 0
            ),
            "last_topup": airtime_transactions[0].get("created_at") if airtime_transactions else None
        }
    
    def _compress_for_bills(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Compress transactions for bill payment patterns"""
        bill_transactions = [t for t in transactions if t.get("intent") == "pay_bill"]
        
        # Analyze by bill type (from category or description)
        bill_stats = defaultdict(lambda: {"count": 0, "total_amount": 0})
        for tx in bill_transactions:
            bill_type = tx.get("category") or tx.get("description", "unknown").split(":")[0]
            bill_stats[bill_type]["count"] += 1
            bill_stats[bill_type]["total_amount"] += tx.get("amount", 0)
        
        return {
            "total_bill_payments": len(bill_transactions),
            "total_amount_paid": sum(tx.get("amount", 0) for tx in bill_transactions),
            "bill_types": dict(bill_stats),
            "average_bill_amount": (
                sum(tx.get("amount", 0) for tx in bill_transactions) / len(bill_transactions) 
                if bill_transactions else 0
            )
        }
    
    def _compress_for_financial_tips(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Compress transactions for general financial tips"""
        return self._compress_for_budgeting(transactions, slots)
    
    def _compress_for_expense_report(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Compress transactions for expense reporting"""
        return self._compress_for_budgeting(transactions, slots)
    
    def _compress_for_investment(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Compress transactions for investment advice (placeholder)"""
        return {
            "message": "Investment analysis requires additional data",
            "total_transactions": len(transactions),
            "transaction_types": list(set(tx.get("intent") for tx in transactions))
        }
    
    def _compress_for_debt(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Compress transactions for debt management (placeholder)"""
        loan_transactions = [t for t in transactions if t.get("intent") == "get_loan"]
        
        return {
            "total_loans": len(loan_transactions),
            "total_loan_amount": sum(tx.get("amount", 0) for tx in loan_transactions),
            "recent_loan": loan_transactions[0] if loan_transactions else None
        }
    
    def _compress_general_transactions(self, transactions: List[Dict], slots: Dict) -> Dict:
        """Default compression for general transaction analysis"""
        return {
            "total_transactions": len(transactions),
            "total_amount": sum(tx.get("amount", 0) for tx in transactions),
            "transaction_types": {
                intent: len([t for t in transactions if t.get("intent") == intent])
                for intent in set(t.get("intent") for t in transactions)
            },
            "recent_activity": [
                {
                    "intent": tx.get("intent"),
                    "amount": tx.get("amount"),
                    "date": tx.get("created_at")
                }
                for tx in transactions[:5]  # Last 5 transactions
            ]
        }
    
    def _generate_budgeting_insights(self, category_spending: Dict, monthly_avg: float) -> List[str]:
        """Generate budgeting insights from spending data"""
        insights = []
        
        if category_spending:
            top_category = max(category_spending.items(), key=lambda x: x[1])
            insights.append(f"Highest spending category: {top_category[0]} (GHS {top_category[1]:.2f})")
            
            if monthly_avg > 1000:  # Example threshold
                insights.append("Monthly spending is above GHS 1000 - consider reviewing discretionary expenses")
        
        return insights
    
    def _generate_savings_insights(self, income: float, expenses: float, savings_rate: float) -> List[str]:
        """Generate savings insights from income/expense data"""
        insights = []
        
        if savings_rate > 20:
            insights.append("Excellent savings rate! You're saving more than 20% of your income")
        elif savings_rate < 10:
            insights.append("Savings rate is below 10% - consider reducing discretionary spending")
        
        if expenses > income:
            insights.append("Spending exceeds income - review expenses immediately")
        
        return insights
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        return len(text) // self.estimated_token_ratio
    
    def _optimize_context_size(self, core_bio: Dict, compressed_data: Dict, intent: str) -> Dict:
        """Ensure total context doesn't exceed token limits"""
        # Convert to JSON string for token estimation
        context_str = json.dumps({
            "core_bio": core_bio,
            "transaction_insights": compressed_data
        }, ensure_ascii=False)
        
        current_tokens = self._estimate_tokens(context_str)
        
        if current_tokens <= self.max_context_tokens:
            return {
                "core_bio": core_bio,
                "transaction_insights": compressed_data,
                "token_usage": current_tokens
            }
        
        # If over limit, apply aggressive compression
        return self._apply_aggressive_compression(core_bio, compressed_data, intent)
    
    def _apply_aggressive_compression(self, core_bio: Dict, compressed_data: Dict, intent: str) -> Dict:
        """Apply more aggressive compression when token limit is exceeded"""
        # Keep only most essential bio data
        essential_bio = {
            "user_id": core_bio.get("user_id"),
            "first_name": core_bio.get("first_name"),
            "member_since": core_bio.get("member_since")
        }
        
        # Keep only summary-level transaction data
        ultra_compressed_data = {
            "summary": compressed_data.get("total_spent") or compressed_data.get("total_transactions"),
            "key_metric": list(compressed_data.values())[0] if compressed_data else "No data"
        }
        
        optimized_context = {
            "core_bio": essential_bio,
            "transaction_insights": ultra_compressed_data,
            "compression_level": "high"
        }
        
        return optimized_context
    
    def format_context_for_prompt(self, user_context: Dict) -> str:
        """Format the user context for inclusion in LLM prompts"""
        core_bio = user_context.get("core_bio", {})
        transaction_insights = user_context.get("transaction_insights", {})
        
        context_parts = []
        
        # Format core bio
        if core_bio:
            bio_lines = ["USER PROFILE:"]
            if core_bio.get("first_name"):
                bio_lines.append(f"- Name: {core_bio['first_name']} {core_bio.get('last_name', '')}".strip())
            if core_bio.get("email"):
                bio_lines.append(f"- Email: {core_bio['email']}")
            if core_bio.get("member_since"):
                bio_lines.append(f"- Member Since: {core_bio['member_since'][:10]}")
            if core_bio.get("location"):
                bio_lines.append(f"- Location: {core_bio['location']}")
            
            context_parts.append("\n".join(bio_lines))
        
        # Format transaction insights
        if transaction_insights and not transaction_insights.get("no_data"):
            insights_lines = ["TRANSACTION INSIGHTS:"]
            
            # Add key metrics
            if "total_spent" in transaction_insights:
                insights_lines.append(f"- Total Spent: GHS {transaction_insights['total_spent']:.2f}")
            if "monthly_average" in transaction_insights:
                insights_lines.append(f"- Monthly Average: GHS {transaction_insights['monthly_average']:.2f}")
            if "savings_rate" in transaction_insights:
                insights_lines.append(f"- Savings Rate: {transaction_insights['savings_rate']:.1f}%")
            if "total_transfers" in transaction_insights:
                insights_lines.append(f"- Money Transfers: {transaction_insights['total_transfers']} transactions")
            
            # Add top spending categories if available
            if "top_spending_categories" in transaction_insights:
                insights_lines.append("- Top Spending Categories:")
                for category, amount in list(transaction_insights["top_spending_categories"].items())[:3]:
                    insights_lines.append(f"  * {category}: GHS {amount:.2f}")
            
            # Add key insights if available
            if "key_insights" in transaction_insights and transaction_insights["key_insights"]:
                insights_lines.append("- Key Patterns:")
                for insight in transaction_insights["key_insights"][:2]:  # Limit to 2 key insights
                    insights_lines.append(f"  * {insight}")
            
            context_parts.append("\n".join(insights_lines))
        
        return "\n\n".join(context_parts)