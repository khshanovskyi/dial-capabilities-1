import os

import uvicorn
from aidial_sdk import DIALApp
from aidial_sdk.chat_completion import ChatCompletion, Request, Response

from app_demo.d5_simple_agent.agent import AgentSample
from app_demo.d5_simple_agent.prompts import SYSTEM_PROMPT
from app_demo.d5_simple_agent.tools.base import BaseTool
from app_demo.d5_simple_agent.tools.deployment.essay_generation_tool import EssayGenerationTool
from app_demo.d5_simple_agent.tools.deployment.image_generation_tool import ImageGenerationTool

DIAL_ENDPOINT = os.getenv('DIAL_ENDPOINT', "http://localhost:8080")
DEPLOYMENT_NAME = os.getenv('DEPLOYMENT_NAME', 'gpt-4o')


class GeneralPurposeAgentApplication(ChatCompletion):

    def __init__(self):
        self.tools: list[BaseTool] = [
            ImageGenerationTool(endpoint=DIAL_ENDPOINT),
            EssayGenerationTool(endpoint=DIAL_ENDPOINT),
        ]

    async def chat_completion(self, request: Request, response: Response) -> None:
        with response.create_single_choice() as choice:
            await AgentSample(
                endpoint=DIAL_ENDPOINT,
                system_prompt=SYSTEM_PROMPT,
                tools=self.tools
            ).handle_request(
                choice=choice,
                deployment_name=DEPLOYMENT_NAME,
                request=request,
                response=response,
            )


app: DIALApp = DIALApp()
agent_app = GeneralPurposeAgentApplication()
app.add_chat_completion(deployment_name="agent-sample", impl=agent_app)

if __name__ == "__main__":
    import sys

    if 'pydevd' in sys.modules:
        config = uvicorn.Config(app, port=5030, host="0.0.0.0", log_level="info")
        server = uvicorn.Server(config)
        import asyncio

        asyncio.run(server.serve())
    else:
        uvicorn.run(app, port=5030, host="0.0.0.0", log_level="info")
