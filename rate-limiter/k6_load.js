import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 5 },   // Ramp up to 5 users
    { duration: '20s', target: 10 },  // Ramp up to 10 users
    { duration: '20s', target: 20 },  // Ramp up to 20 users (should trigger rate limits)
    { duration: '10s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.5'],  // Allow some failures due to rate limiting
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // Test root endpoint
  let response = http.get(`${BASE_URL}/`);
  
  check(response, {
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
    'has rate limit headers': (r) => r.headers['X-RateLimit-Limit'] !== undefined,
  });
  
  // Test API endpoint
  response = http.get(`${BASE_URL}/api/data`);
  
  check(response, {
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
    'has remaining header': (r) => r.headers['X-RateLimit-Remaining'] !== undefined,
  });
  
  // Test POST endpoint
  const payload = JSON.stringify({ test: 'data', timestamp: Date.now() });
  response = http.post(`${BASE_URL}/api/submit`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });
  
  check(response, {
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
  });
  
  sleep(0.1); // Small delay between requests
}

export function handleSummary(data) {
  return {
    'stdout': JSON.stringify(data, null, 2),
  };
}

