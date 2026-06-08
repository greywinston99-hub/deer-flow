import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const directEnv = {
  HTTP_PROXY: "",
  HTTPS_PROXY: "",
  ALL_PROXY: "",
  http_proxy: "",
  https_proxy: "",
  all_proxy: "",
  NO_PROXY: "*",
  no_proxy: "*",
};

const timestamp = new Date().toISOString().replace(/[-:T.Z]/g, "").slice(0, 14);

function backup(file) {
  if (fs.existsSync(file)) {
    fs.copyFileSync(file, `${file}.bak.direct_network_${timestamp}`);
  }
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function writeJson(file, data) {
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`);
}

function ensureClaudeSettings(file) {
  const settings = readJson(file);
  settings.env = { ...(settings.env || {}), ...directEnv };
  writeJson(file, settings);
}

function ensureVsCodeSettings(file) {
  const settings = readJson(file);
  settings["http.proxySupport"] = "off";
  settings["http.proxy"] = "";
  settings["http.proxyStrictSSL"] = true;

  const existing = Array.isArray(settings["claudeCode.environmentVariables"])
    ? settings["claudeCode.environmentVariables"]
    : [];
  const byName = new Map();
  for (const item of existing) {
    if (item && typeof item.name === "string") {
      byName.set(item.name, { ...item });
    }
  }
  for (const [name, value] of Object.entries(directEnv)) {
    byName.set(name, { name, value });
  }
  settings["claudeCode.environmentVariables"] = [...byName.values()];
  writeJson(file, settings);
}

function updateEnvFile(file) {
  const lines = fs.existsSync(file) ? fs.readFileSync(file, "utf8").split(/\r?\n/) : [];
  const keys = new Set(Object.keys(directEnv));
  const output = [];
  const seen = new Set();
  for (const line of lines) {
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=/);
    if (match && keys.has(match[1])) {
      const key = match[1];
      output.push(`${key}=${directEnv[key]}`);
      seen.add(key);
    } else if (line !== "" || output.length) {
      output.push(line);
    }
  }
  for (const [key, value] of Object.entries(directEnv)) {
    if (!seen.has(key)) {
      output.push(`${key}=${value}`);
    }
  }
  fs.writeFileSync(file, `${output.join("\n").replace(/\n+$/g, "")}\n`);
}

const home = os.homedir();
const files = {
  claudeSettings: path.join(home, ".claude", "settings.json"),
  routerEnv: path.join(home, ".claude", "provider-router.env"),
  vscodeSettings: path.join(home, "Library", "Application Support", "Code", "User", "settings.json"),
};

for (const file of Object.values(files)) {
  backup(file);
}
ensureClaudeSettings(files.claudeSettings);
updateEnvFile(files.routerEnv);
ensureVsCodeSettings(files.vscodeSettings);

console.log(JSON.stringify({ ok: true, files }, null, 2));
