import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { initializeApp } from "firebase-admin/app";
import { getDataConnect } from "firebase-admin/data-connect";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const connectorRoot = path.join(projectRoot, "dataconnect", "example");
const operations = {
  create_ticket: ["CreateSupportTicket.gql", "write"],
  get_ticket: ["GetSupportTicket.gql", "read"],
  list_tickets: ["ListSupportTickets.gql", "read"],
  update_email_status: ["UpdateTicketEmailStatus.gql", "write"],
  resolve_ticket: ["ResolveSupportTicket.gql", "write"],
};

function getErrorCode(error) {
  const code = typeof error?.code === "string" ? error.code.toLowerCase() : "";
  const message = typeof error?.message === "string" ? error.message.toLowerCase() : "";
  if (message.includes("default credentials")) return "ADC_CREDENTIALS_MISSING";
  if (code.includes("permission-denied")) return "PERMISSION_DENIED";
  if (code.includes("unauthenticated")) return "UNAUTHENTICATED";
  if (code.includes("invalid-credential")) return "INVALID_CREDENTIAL";
  if (code.includes("not-found")) return "DATACONNECT_NOT_FOUND";
  if (code === "graphql_operation_failed") return "GRAPHQL_OPERATION_FAILED";
  return "DATACONNECT_ERROR";
}

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const request = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  const operation = operations[request.operation];
  if (!operation) throw new Error("UNKNOWN_OPERATION");

  const query = await readFile(path.join(connectorRoot, operation[0]), "utf8");
  const app = initializeApp({
    projectId: process.env.FIREBASE_PROJECT_ID || "soporteit-tickets",
  });
  try {
    const dataConnect = getDataConnect({
      serviceId: process.env.DATA_CONNECT_SERVICE_ID || "soporteit-tickets-service",
      location: process.env.DATA_CONNECT_LOCATION || "us-east4",
    });
    const options = { variables: request.variables || {} };
    const result = operation[1] === "read"
      ? await dataConnect.executeGraphqlRead(query, options)
      : await dataConnect.executeGraphql(query, options);
    if (result.errors?.length) {
      const error = new Error("GraphQL operation failed");
      error.code = "GRAPHQL_OPERATION_FAILED";
      throw error;
    }
    process.stdout.write(JSON.stringify(result.data ?? {}));
  } finally {
    await app.delete();
  }
}

main().catch((error) => {
  process.stderr.write(JSON.stringify({ error: getErrorCode(error) }));
  process.exitCode = 1;
});
