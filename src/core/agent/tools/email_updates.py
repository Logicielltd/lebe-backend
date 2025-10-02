from typing import Any, Optional
from smolagents.tools import Tool

class CheckEmailNotificationsTool(Tool):
    name = "check_email_notifications"
    description = "Check for new email notifications in the specified email account."
    inputs = {
        'email_account': {
            'type': 'string', 
            'description': 'Email account to check (default: "default")',
            'default': 'default',
             'nullable': True
        },
        'max_emails': {
            'type': 'integer',
            'description': 'Maximum number of recent emails to return',
            'default': 5,
             'nullable': True
        }
    }
    output_type = "string"

    def forward(self, email_account: str = "default", max_emails: int = 5) -> str:
        """Check for new email notifications in the specified email account."""
        try:
            # For security reasons, this is a simulated version
            # In production, you'd integrate with actual email APIs
            
            # Simulated email data
            simulated_emails = [
                {
                    'subject': 'Invoice #INV-2024-001 Approved',
                    'from': 'accounting@company.com',
                    'date': '2024-01-15 10:30:45',
                    'priority': 'high',
                    'category': 'finance'
                },
                {
                    'subject': 'New Customer Registration: John Smith',
                    'from': 'crm@company.com', 
                    'date': '2024-01-15 09:15:22',
                    'priority': 'medium',
                    'category': 'sales'
                },
                {
                    'subject': 'Inventory Alert: Product XYZ low stock',
                    'from': 'inventory@company.com',
                    'date': '2024-01-15 08:45:10',
                    'priority': 'high',
                    'category': 'operations'
                },
                {
                    'subject': 'Monthly Team Meeting Reminder',
                    'from': 'calendar@company.com',
                    'date': '2024-01-14 16:20:33',
                    'priority': 'low',
                    'category': 'general'
                }
            ]
            
            result = f"📧 Email notifications for account: {email_account}\n\n"
            result += f"Found {len(simulated_emails)} recent emails:\n\n"
            
            for i, email in enumerate(simulated_emails[:max_emails], 1):
                result += f"{i}. [{email['priority'].upper()}] {email['subject']}\n"
                result += f"   From: {email['from']}\n"
                result += f"   Date: {email['date']}\n"
                result += f"   Category: {email['category']}\n\n"
            
            result += "💡 Tip: Use 'execute_business_process' to handle any urgent matters."
            return result
            
        except Exception as e:
            return f"Error checking email notifications: {str(e)}"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)