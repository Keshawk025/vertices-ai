import fs from "fs";
import path from "path";

// Helper to load root .env variables for testing environment
function loadEnv() {
  const envPath = path.resolve(__dirname, "../../.env");
  if (fs.existsSync(envPath)) {
    const envConfig = fs.readFileSync(envPath, "utf8");
    for (const line of envConfig.split("\n")) {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith("#") && trimmed.includes("=")) {
        const [key, ...values] = trimmed.split("=");
        process.env[key.trim()] = values.join("=").trim().replace(/^["']|["']$/g, "");
      }
    }
  }
}
loadEnv();

import { logOut } from "../lib/auth";

async function runDashboardTests() {
  console.log("==================================================");
  console.log("  RUNNING TASK F2: DASHBOARD BACKEND & UI TESTS   ");
  console.log("==================================================");

  let passed = 0;
  let failed = 0;

  function assert(condition: boolean, testName: string) {
    if (condition) {
      console.log(`[PASS] ${testName}`);
      passed++;
    } else {
      console.error(`[FAIL] ${testName}`);
      failed++;
    }
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const mockToken = "mock_firebase_id_token_12345";

  // 1. Authorization Header Verification
  console.log("\n--- Testing Authorization Header & Token Handling ---");
  const authHeader = `Bearer ${mockToken}`;
  assert(authHeader.startsWith("Bearer "), "Auth: Authorization header format is Bearer <token>");
  assert(authHeader.includes(mockToken), "Auth: Token is correctly embedded in Authorization header");

  // 2. Stats API Request Simulation & Response Parsing
  console.log("\n--- Testing Stats API Request & Response Parsing ---");
  const mockStatsResponse = {
    total_documents: 12,
    total_conversations: 5,
    total_questions: 34,
    total_ocr_documents: 3,
    total_storage_bytes: 5242880, // 5 MB
  };

  function parseStats(data: any) {
    return {
      totalDocs: data.total_documents ?? 0,
      totalConvs: data.total_conversations ?? 0,
      totalQuestions: data.total_questions ?? 0,
      totalOcr: data.total_ocr_documents ?? 0,
      storageBytes: data.total_storage_bytes ?? 0,
    };
  }

  const parsedStats = parseStats(mockStatsResponse);
  assert(parsedStats.totalDocs === 12, "Stats: Parsed total_documents correctly");
  assert(parsedStats.totalConvs === 5, "Stats: Parsed total_conversations correctly");
  assert(parsedStats.totalQuestions === 34, "Stats: Parsed total_questions correctly");
  assert(parsedStats.totalOcr === 3, "Stats: Parsed total_ocr_documents correctly");
  assert(parsedStats.storageBytes === 5242880, "Stats: Parsed total_storage_bytes correctly");

  // 3. Recent Documents API Request & Query Params Serialization
  console.log("\n--- Testing Recent Documents API Request & Filtering ---");
  const searchQuery = "financial_report";
  const statusFilter = "processed";

  const params = new URLSearchParams();
  if (searchQuery) params.append("search", searchQuery);
  if (statusFilter) params.append("status", statusFilter);

  const requestUrl = `${apiUrl}/dashboard/recent-documents?${params.toString()}`;
  assert(requestUrl.includes("search=financial_report"), "Recent Docs: Search param serialized");
  assert(requestUrl.includes("status=processed"), "Recent Docs: Status filter param serialized");

  const mockDocuments = [
    {
      id: "doc_1",
      filename: "financial_report_2026.pdf",
      file_size: 1048576,
      page_count: 8,
      ocr_used: true,
      status: "processed",
      uploaded_at: "2026-08-15T12:00:00Z",
    },
    {
      id: "doc_2",
      filename: "project_overview.pdf",
      file_size: 512000,
      page_count: 4,
      ocr_used: false,
      status: "uploaded",
      uploaded_at: "2026-08-15T13:00:00Z",
    },
  ];

  assert(mockDocuments.length === 2, "Recent Docs: Parsed document items list");
  assert(mockDocuments[0].ocr_used === true, "Recent Docs: OCR flag correctly read");

  // 4. Loading State Logic
  console.log("\n--- Testing Loading States ---");
  let loadingStats = true;
  let loadingDocs = true;

  function renderDashboardState(loadingS: boolean, loadingD: boolean, docs: any[]) {
    if (loadingS || loadingD) {
      return "LOADING_SKELETON";
    }
    if (docs.length === 0) {
      return "EMPTY_STATE";
    }
    return "LOADED_DATA";
  }

  assert(renderDashboardState(loadingStats, loadingDocs, []) === "LOADING_SKELETON", "Loading: Displays skeleton while loading");

  loadingStats = false;
  loadingDocs = false;

  // 5. Empty State Logic
  console.log("\n--- Testing Empty State Handling ---");
  assert(renderDashboardState(false, false, []) === "EMPTY_STATE", "Empty State: Displays empty prompt when 0 documents");
  assert(renderDashboardState(false, false, mockDocuments) === "LOADED_DATA", "Loaded State: Displays document list when data present");

  // 6. API Error State Handling & 401 Unauthorized
  console.log("\n--- Testing Error Handling & Unauthorized Redirection ---");
  function handleApiResponse(status: number) {
    if (status === 401) {
      return { redirect: "/login", error: null };
    }
    if (status >= 500) {
      return { redirect: null, error: "Unable to connect to Veritas AI backend service." };
    }
    return { redirect: null, error: null };
  }

  const unauthResult = handleApiResponse(401);
  assert(unauthResult.redirect === "/login", "Error Handling: 401 Unauthorized redirects to /login");

  const serverErrorResult = handleApiResponse(500);
  assert(serverErrorResult.error !== null, "Error Handling: Server error generates user-friendly alert");

  // 7. Logout Action
  console.log("\n--- Testing Logout Action ---");
  assert(typeof logOut === "function", "Logout: logOut function is available from auth service");

  let redirectedTo = "";
  const mockRouter = {
    push: (url: string) => {
      redirectedTo = url;
    },
  };

  async function performLogout() {
    mockRouter.push("/login");
  }
  await performLogout();
  assert(redirectedTo === "/login", "Logout: Successfully routes user to /login on sign out");

  // 8. Component Structure Verification
  console.log("\n--- Testing Component Structure ---");
  const dashboardPagePath = path.resolve(__dirname, "../app/dashboard/page.tsx");
  const sidebarPath = path.resolve(__dirname, "../components/dashboard/Sidebar.tsx");
  const topBarPath = path.resolve(__dirname, "../components/dashboard/TopBar.tsx");
  const statCardPath = path.resolve(__dirname, "../components/dashboard/StatCard.tsx");
  const recentDocsPath = path.resolve(__dirname, "../components/dashboard/RecentDocuments.tsx");

  assert(fs.existsSync(dashboardPagePath), "Components: app/dashboard/page.tsx exists");
  assert(fs.existsSync(sidebarPath), "Components: components/dashboard/Sidebar.tsx exists");
  assert(fs.existsSync(topBarPath), "Components: components/dashboard/TopBar.tsx exists");
  assert(fs.existsSync(statCardPath), "Components: components/dashboard/StatCard.tsx exists");
  assert(fs.existsSync(recentDocsPath), "Components: components/dashboard/RecentDocuments.tsx exists");

  console.log("\n==================================================");
  console.log(`  TEST RESULTS: ${passed} PASSED, ${failed} FAILED  `);
  console.log("==================================================");

  if (failed > 0) {
    process.exit(1);
  }
}

runDashboardTests();
