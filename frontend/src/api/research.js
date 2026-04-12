import service, { requestWithRetry } from './index'

/**
 * Phase 8 — Research-from-prompt module API client.
 *
 * All endpoints are mounted at /api/research/* by the backend's optional
 * research blueprint (only when RESEARCH_ENABLED=true). The frontend calls
 * /availability on Step 0 mount to detect whether the module is enabled
 * at all (404 = disabled, 200 = enabled with runner list).
 */

/**
 * Probe which runners are installed and authenticated on the host.
 * Returns 404 if the research module is disabled — callers should treat
 * that as "research feature not available" and hide the Step 0 entry point.
 */
export function getResearchAvailability() {
  return requestWithRetry(() =>
    service({
      url: '/api/research/availability',
      method: 'get',
    })
  )
}

/**
 * Begin a research task. Spawns a background thread on the backend; the
 * frontend then polls /status/<task_id> for progress.
 *
 * @param {Object} params
 * @param {string} params.prompt - vague intent, e.g. "predict EV truck adoption"
 * @param {string} params.simulation_requirement - what the user wants to simulate
 * @param {string} params.runner_choice - which runner to use (claude/codex/kimi/api)
 * @param {string} [params.project_name]
 * @param {string} [params.additional_context]
 */
export function startResearch(params) {
  return requestWithRetry(() =>
    service({
      url: '/api/research/start',
      method: 'post',
      data: params,
    })
  )
}

/**
 * Poll task status. Safe to call repeatedly; returns slim payload (no compiled_text).
 */
export function getResearchStatus(taskId) {
  return service({
    url: `/api/research/status/${taskId}`,
    method: 'get',
  })
}

/**
 * Fetch the full compiled document + citations for a completed task.
 * Returns 409 if the task is not yet in the COMPLETED phase.
 */
export function getResearchResult(taskId) {
  return requestWithRetry(() =>
    service({
      url: `/api/research/result/${taskId}`,
      method: 'get',
    })
  )
}

/**
 * Promote a completed research task into the existing project pipeline:
 * writes the compiled document to the project's extracted_text.txt and
 * returns the project_id so the frontend can transition to Step 1.
 */
export function promoteResearch(taskId) {
  return requestWithRetry(() =>
    service({
      url: `/api/research/promote/${taskId}`,
      method: 'post',
    })
  )
}

/**
 * Request cancellation of an in-flight research task. The orchestrator
 * polls cooperatively at phase boundaries.
 */
export function cancelResearch(taskId) {
  return service({
    url: `/api/research/cancel/${taskId}`,
    method: 'post',
  })
}
