export interface SchedulerEnv {
  GITHUB_TOKEN?: string;
}

const DISPATCH_URL =
  "https://api.github.com/repos/lovemonlin/iceland-aurora-cloud/actions/workflows/update-road-info.yml/dispatches";
const USER_AGENT = "iceland-aurora-road-scheduler";
const MISSING_TOKEN_MESSAGE = "IRCA road scheduler: GITHUB_TOKEN is not configured.";
const DISPATCH_FAILURE_MESSAGE = "IRCA road scheduler: GitHub dispatch did not return 204.";
const NETWORK_FAILURE_MESSAGE = "IRCA road scheduler: GitHub dispatch request failed.";

function fail(message: string): never {
  console.error(message);
  throw new Error(message);
}

const worker = {
  async scheduled(_controller: unknown, env: SchedulerEnv, _ctx: unknown): Promise<void> {
    if (!env.GITHUB_TOKEN) fail(MISSING_TOKEN_MESSAGE);

    let response: Response;
    try {
      response = await globalThis.fetch(DISPATCH_URL, {
        method: "POST",
        redirect: "manual",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          "Content-Type": "application/json",
          "User-Agent": USER_AGENT,
          "X-GitHub-Api-Version": "2022-11-28",
        },
        body: JSON.stringify({ ref: "main" }),
      });
    } catch {
      fail(NETWORK_FAILURE_MESSAGE);
    }

    if (response.status !== 204) fail(DISPATCH_FAILURE_MESSAGE);
  },

  fetch(): Response {
    return Response.json({ ok: true, service: "irca-road-scheduler" });
  },
};

export default worker;
