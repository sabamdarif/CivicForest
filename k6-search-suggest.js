// k6 load test for /api/v1/search/suggest — the one endpoint designed to be hammered.
// Run: k6 run k6-search-suggest.js
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 20 }, // ramp to 20 VUs
    { duration: "1m", target: 50 },  // sustain 50 VUs
    { duration: "20s", target: 0 },  // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"], // 95th percentile under 500ms
    http_req_failed: ["rate<0.05"],   // <5% errors
  },
};

const BASE = __ENV.API_URL || "http://localhost:8000";
const QUERIES = ["tee", "hoodie", "black", "green", "classic", "signature"];

export default function () {
  const q = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  const res = http.get(`${BASE}/api/v1/search/suggest?q=${q}`);
  check(res, {
    "status 200": (r) => r.status === 200,
    "hits array present": (r) => Array.isArray(JSON.parse(r.body).hits),
  });
  sleep(1); // 1s between requests per VU
}
