import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 10 },  // Ramp up to 10 users
    { duration: '30s', target: 20 },   // Ramp up to 20 users
    { duration: '30s', target: 30 },   // Sustained high load
    { duration: '10s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'], // Cached responses should be fast
    http_req_failed: ['rate<0.05'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Feature flags to test
const flags = [
  'new_checkout_flow',
  'beta_features',
  'dark_mode',
  'experimental_api'
];

// Generate user IDs for consistent rollout
const userIds = [];
for (let i = 0; i < 50; i++) {
  userIds.push(`user_${i}`);
}

export default function () {
  // Randomly select flag and user
  const flagName = flags[Math.floor(Math.random() * flags.length)];
  const userId = Math.random() < 0.7 
    ? userIds[Math.floor(Math.random() * userIds.length)]
    : null;
  
  // Test flag check endpoint (most common operation)
  const url = userId
    ? `${BASE_URL}/flags/${flagName}/check?user_id=${userId}`
    : `${BASE_URL}/flags/${flagName}/check`;
  
  let response = http.get(url);
  
  check(response, {
    'status is 200': (r) => r.status === 200,
    'has enabled field': (r) => {
      const body = JSON.parse(r.body);
      return body.enabled !== undefined;
    },
    'response time acceptable': (r) => r.timings.duration < 100,
  });
  
  // Check cache hit rate
  const body = JSON.parse(response.body);
  if (body._cache === 'hit') {
    // Cache hit - should be very fast
    check(response, {
      'cached response is fast': (r) => r.timings.duration < 50,
    });
  }
  
  // Occasionally test full flag endpoint
  if (Math.random() < 0.2) {
    const fullUrl = userId
      ? `${BASE_URL}/flags/${flagName}?user_id=${userId}`
      : `${BASE_URL}/flags/${flagName}`;
    
    response = http.get(fullUrl);
    
    check(response, {
      'full endpoint works': (r) => r.status === 200,
    });
  }
  
  // Occasionally list all flags
  if (Math.random() < 0.1) {
    response = http.get(`${BASE_URL}/flags`);
    
    check(response, {
      'list flags works': (r) => r.status === 200,
    });
  }
  
  // Very rarely update a flag (to test cache invalidation)
  if (Math.random() < 0.01) {
    const updateFlag = flags[Math.floor(Math.random() * flags.length)];
    response = http.post(
      `${BASE_URL}/flags/${updateFlag}/update?enabled=true&rollout_percentage=50`
    );
    
    check(response, {
      'flag update works': (r) => r.status === 200,
    });
  }
  
  sleep(0.1);
}

export function handleSummary(data) {
  // Calculate cache hit rate
  const totalRequests = data.metrics.http_reqs.values.count;
  // Note: Cache hit rate would need to be tracked separately in production
  
  return {
    'stdout': JSON.stringify(data, null, 2),
  };
}

