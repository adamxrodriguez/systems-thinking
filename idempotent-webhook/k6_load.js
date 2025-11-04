import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 5 },   // Ramp up to 5 users
    { duration: '20s', target: 10 },  // Ramp up to 10 users
    { duration: '20s', target: 15 },  // Sustained load
    { duration: '10s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.1'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Generate unique idempotency keys for testing
const idempotencyKeys = [];

export function setup() {
  // Generate pool of idempotency keys
  for (let i = 0; i < 100; i++) {
    idempotencyKeys.push(`test-key-${i}`);
  }
  return { idempotencyKeys };
}

export default function (data) {
  // Randomly choose: use idempotency key or not (70% use key)
  const useIdempotency = Math.random() < 0.7;
  
  // Select idempotency key (may reuse)
  const keyIndex = Math.floor(Math.random() * data.idempotencyKeys.length);
  const idempotencyKey = data.idempotencyKeys[keyIndex];
  
  const payload = JSON.stringify({
    event: 'payment.received',
    data: {
      payment_id: `pay_${Date.now()}_${Math.random()}`,
      amount: Math.floor(Math.random() * 10000) / 100,
      currency: 'USD',
      timestamp: new Date().toISOString()
    }
  });

  const headers = {
    'Content-Type': 'application/json',
  };

  // Add idempotency key if using idempotency
  if (useIdempotency) {
    headers['X-Idempotency-Key'] = idempotencyKey;
  }

  // Send webhook
  let response = http.post(`${BASE_URL}/webhook`, payload, { headers });

  check(response, {
    'status is 200': (r) => r.status === 200,
    'has response body': (r) => r.body.length > 0,
  });

  // If using idempotency, send duplicate request
  if (useIdempotency && Math.random() < 0.3) {
    sleep(0.1);
    
    // Send same request again (should be cached)
    response = http.post(`${BASE_URL}/webhook`, payload, { headers });
    
    check(response, {
      'duplicate request returns cached': (r) => r.status === 200,
      'has cached header': (r) => r.headers['X-Cached'] === 'true',
    });
  }

  // Occasionally check idempotency status
  if (useIdempotency && Math.random() < 0.1) {
    response = http.get(`${BASE_URL}/webhook/idempotency/${idempotencyKey}`);
    check(response, {
      'idempotency status available': (r) => r.status === 200,
    });
  }

  sleep(0.5);
}

export function handleSummary(data) {
  return {
    'stdout': JSON.stringify(data, null, 2),
  };
}

