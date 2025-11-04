import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 5 },   // Ramp up to 5 users
    { duration: '20s', target: 10 },   // Ramp up to 10 users
    { duration: '20s', target: 15 },   // Sustained load
    { duration: '10s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],
    http_req_failed: ['rate<0.1'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Generate random recipient lists
function generateRecipients() {
  const count = Math.floor(Math.random() * 5) + 1; // 1-5 recipients
  const recipients = [];
  for (let i = 0; i < count; i++) {
    recipients.push(`user${Math.floor(Math.random() * 1000)}@example.com`);
  }
  return recipients;
}

export default function () {
  // Create notification
  const payload = JSON.stringify({
    recipients: generateRecipients(),
    message: {
      subject: `Test Notification ${Date.now()}`,
      body: 'This is a test notification message',
      type: 'email'
    }
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  // Enqueue notification
  let response = http.post(`${BASE_URL}/notifications`, payload, params);

  check(response, {
    'status is 200': (r) => r.status === 200,
    'has job_id': (r) => {
      const body = JSON.parse(r.body);
      return body.job_id !== undefined;
    },
  });

  if (response.status === 200) {
    const body = JSON.parse(response.body);
    const jobId = body.job_id;

    // Check job status
    sleep(1);
    response = http.get(`${BASE_URL}/notifications/${jobId}`);

    check(response, {
      'status check succeeds': (r) => r.status === 200,
      'job status present': (r) => {
        const body = JSON.parse(r.body);
        return body.status !== undefined;
      },
    });
  }

  // Check DLQ stats occasionally
  if (Math.random() < 0.1) {
    response = http.get(`${BASE_URL}/notifications/dlq/stats`);
    check(response, {
      'DLQ stats available': (r) => r.status === 200,
    });
  }

  sleep(0.5);
}

export function handleSummary(data) {
  return {
    'stdout': JSON.stringify(data, null, 2),
  };
}

