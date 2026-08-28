import axios from 'axios';
import { agentBaseUrl } from '../config/config';

const agentService = axios.create({
  baseURL: agentBaseUrl,
  timeout: 20000
});

export function eventStreamUrl(threadId, runId, after = 0) {
  return `${agentBaseUrl}/api/agent/threads/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}/events?after=${after}`;
}

export default agentService;
