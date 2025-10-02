from smolagents import CodeAgent,DuckDuckGoSearchTool, HfApiModel,load_tool,tool
import datetime
import requests
import pytz
import yaml
from tools.final_answer import FinalAnswerTool

from Gradio_UI import GradioUI

# Below is an example of a tool that does nothing. Amaze us with your creativity !
@tool
def check_email_notifications(email_account: str = "default", max_emails: int = 5) -> str:
    """Check for new email notifications in the specified email account.
    
    Args:
        email_account: Email account to check (default: 'default')
        max_emails: Maximum number of recent emails to return
    """
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

@tool
def get_current_time_in_timezone(timezone: str) -> str:
    """A tool that fetches the current local time in a specified timezone.
    Args:
        timezone: A string representing a valid timezone (e.g., 'America/New_York').
    """
    try:
        # Create timezone object
        tz = pytz.timezone(timezone)
        # Get current time in that timezone
        local_time = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        return f"The current local time in {timezone} is: {local_time}"
    except Exception as e:
        return f"Error fetching time for timezone '{timezone}': {str(e)}"


final_answer = FinalAnswerTool()

# If the agent does not answer, the model is overloaded, please use another model or the following Hugging Face Endpoint that also contains qwen2.5 coder:
# model_id='https://pflgm2locj2t89co.us-east-1.aws.endpoints.huggingface.cloud' 

model = HfApiModel(
max_tokens=2096,
temperature=0.5,
model_id='Qwen/Qwen2.5-Coder-32B-Instruct',# it is possible that this model may be overloaded
custom_role_conversions=None,
)


# Import tool from Hub
image_generation_tool = load_tool("agents-course/text-to-image", trust_remote_code=True)

with open("src/core/agent/prompts.yaml", 'r') as stream:
    prompt_templates = yaml.safe_load(stream)
    
agent = CodeAgent(
    model=model,
    tools=[final_answer, get_current_time_in_timezone, check_email_notifications, image_generation_tool, DuckDuckGoSearchTool()],
    max_steps=6,
    verbosity_level=1,
    grammar=None,
    planning_interval=None,
    name=None,
    description=None,
    prompt_templates=prompt_templates
)

# Run the agent and capture the response
response = agent.run("hello assistant")

print("Freds Final Answer:", response)

#GradioUI(agent).launch()