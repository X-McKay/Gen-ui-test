/**
 * CopilotKit runtime (v2) for the Next.js App Router. It proxies the browser to the
 * AG-UI agent served by the FastAPI backend and applies the generative-UI middleware,
 * which validates every `render_ui` operation against the catalog before it is streamed on.
 */
import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, InMemoryAgentRunner, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const runtime = new CopilotRuntime({
  agents: {
    intake: new HttpAgent({ url: `${backendUrl}/agent` }),
  },
  runner: new InMemoryAgentRunner(),
  // Applied when the provider sends a tool-transport envelope; `true` forces it on every run.
  generativeUI: true,
});

const handler = createCopilotRuntimeHandler({ runtime, basePath: "/api/copilotkit" });

export const dynamic = "force-dynamic";
export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
export const OPTIONS = handler;
