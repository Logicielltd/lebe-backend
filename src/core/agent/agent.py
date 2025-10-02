from smolagents import CodeAgent, DuckDuckGoSearchTool, HfApiModel, load_tool, tool
import datetime
import requests
import pytz
import yaml
from core.agent.tools.final_answer import FinalAnswerTool
from core.agent.tools.email_updates import CheckEmailNotificationsTool


class BusinessAssistant:
    def __init__(self, model_id='Qwen/Qwen2.5-Coder-32B-Instruct', max_tokens=2096, temperature=0.5):
        """
        Initialize the Business Assistant agent.
        
        Args:
            model_id: Hugging Face model ID or endpoint URL
            max_tokens: Maximum tokens for model response
            temperature: Temperature for model sampling
        """
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.agent = None
        self.initialize_agent()
    
    def initialize_agent(self):
        """Initialize the agent with tools and configuration."""
        
        
        # Initialize model
        model = HfApiModel(
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            model_id=self.model_id,
            custom_role_conversions=None,
        )
        
        # Load tools
        image_generation_tool = load_tool("agents-course/text-to-image", trust_remote_code=True)
        final_answer = FinalAnswerTool()
        email_tool = CheckEmailNotificationsTool()
        
        # Load prompt templates
        with open("src/core/agent/prompts.yaml", 'r') as stream:
            prompt_templates = yaml.safe_load(stream)
        
        # Initialize agent
        self.agent = CodeAgent(
            model=model,
            tools=[final_answer, email_tool, image_generation_tool, 
                  DuckDuckGoSearchTool()],
            max_steps=6,
            verbosity_level=1,
            grammar=None,
            planning_interval=None,
            name=None,
            description=None,
            prompt_templates=prompt_templates
        )

    def process_query(self, query: str) -> str:
        """
        Process a user query using the agent.
        
        Args:
            query: The user's input query
            
        Returns:
            The agent's response
        """
        if not self.agent:
            self.initialize_agent()
        
        try:
            response = self.agent.run(query)
            return response
        except Exception as e:
            return f"Error processing query: {str(e)}"
    
    def launch_ui(self):
        """Launch the Gradio UI (optional)."""
        from Gradio_UI import GradioUI
        return GradioUI(self.agent).launch()