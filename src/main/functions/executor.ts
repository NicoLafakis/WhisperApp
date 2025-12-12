/**
 * JARVIS Voice Agent - Function Executor
 * Executes system functions with proper error handling and security
 */

import { exec, spawn } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as os from 'os';
import { logger } from '../../shared/utils/logger';

const execAsync = promisify(exec);

// Security configuration
const SECURITY_CONFIG = {
  // Allowed base directories for file operations
  allowedBasePaths: [
    os.homedir(),
    os.tmpdir(),
    process.cwd(),
  ],

  // Dangerous command patterns to block
  dangerousPatterns: [
    /rm\s+(-rf?|--recursive|--force)/i,
    /del\s+\/[sfq]/i,
    /format\s+[a-z]:/i,
    /diskpart/i,
    /reg\s+(delete|add)/i,
    /net\s+(user|localgroup)/i,
    /takeown/i,
    /icacls.*\/grant/i,
    /shutdown/i,
    /bcdedit/i,
    /sfc\s+\/scannow/i,
    /cipher\s+\/w/i,
    /attrib\s+[+-][srha]/i,
    /\|\s*rm/i,
    /;\s*rm/i,
    /`rm/i,
    /\$\(.*rm/i,
  ],

  // Allowed command prefixes (whitelist approach for safer operation)
  allowedCommandPrefixes: [
    'get-',
    'dir',
    'ls',
    'echo',
    'write-output',
    'select-',
    'where-object',
    'measure-object',
    'sort-object',
    'format-',
    'out-string',
    'test-path',
    'get-content',
    'get-childitem',
    'get-process',
    'get-service',
    'get-date',
    'get-location',
    '[datetime]',
    '[math]',
  ],

  // Maximum command length
  maxCommandLength: 500,

  // Maximum file size to read (10MB)
  maxFileSize: 10 * 1024 * 1024,
};

export type ConfirmationCallback = (
  functionName: string,
  args: Record<string, any>,
  description: string
) => Promise<boolean>;

export class FunctionExecutor {
  private blockedFunctions: Set<string> = new Set();
  private confirmationRequired: Set<string> = new Set();
  private confirmationCallback: ConfirmationCallback | null = null;
  private pendingConfirmations: Map<string, { resolve: (v: boolean) => void; reject: (e: Error) => void }> = new Map();

  constructor(blockedFunctions: string[] = [], confirmationRequired: string[] = []) {
    this.blockedFunctions = new Set(blockedFunctions);
    this.confirmationRequired = new Set(confirmationRequired);
  }

  /**
   * Set a callback for handling confirmation requests
   */
  setConfirmationCallback(callback: ConfirmationCallback) {
    this.confirmationCallback = callback;
  }

  /**
   * Respond to a pending confirmation request
   */
  respondToConfirmation(confirmationId: string, approved: boolean) {
    const pending = this.pendingConfirmations.get(confirmationId);
    if (pending) {
      pending.resolve(approved);
      this.pendingConfirmations.delete(confirmationId);
    }
  }

  async execute(functionName: string, args: Record<string, any>): Promise<any> {
    logger.info('Executing function', { functionName, args });

    // Check if function is blocked
    if (this.blockedFunctions.has(functionName)) {
      throw new Error(`Function ${functionName} is blocked for security reasons`);
    }

    // Check if confirmation is required
    if (this.confirmationRequired.has(functionName)) {
      const approved = await this.requestConfirmation(functionName, args);
      if (!approved) {
        throw new Error(`Function ${functionName} was not approved by user`);
      }
    }

    try {
      const result = await this.executeFunction(functionName, args);
      logger.info('Function executed successfully', { functionName, result });
      return result;
    } catch (error: any) {
      logger.error('Function execution failed', { functionName, error: error.message });
      throw error;
    }
  }

  private async requestConfirmation(functionName: string, args: Record<string, any>): Promise<boolean> {
    const description = this.getConfirmationDescription(functionName, args);

    if (this.confirmationCallback) {
      logger.warn('Requesting user confirmation', { functionName, description });
      return await this.confirmationCallback(functionName, args, description);
    }

    // If no callback is set, log warning and deny by default for safety
    logger.warn('Function requires confirmation but no callback set - denying', { functionName });
    return false;
  }

  private getConfirmationDescription(functionName: string, args: Record<string, any>): string {
    switch (functionName) {
      case 'delete_file':
        return `Delete file: ${args.path}`;
      case 'execute_command':
        return `Execute command: ${args.command}`;
      case 'move_file':
        return `Move file from ${args.source} to ${args.destination}`;
      case 'create_file':
        return `Create file: ${args.path}`;
      default:
        return `Execute ${functionName} with args: ${JSON.stringify(args)}`;
    }
  }

  private async executeFunction(functionName: string, args: Record<string, any>): Promise<any> {
    switch (functionName) {
      case 'launch_application':
        return this.launchApplication(args as { name: string; args?: string[]; cwd?: string });

      case 'open_file':
        return this.openFile(args as { path: string });

      case 'execute_command':
        return this.executeCommand(args as { command: string });

      case 'query_system_state':
        return this.querySystemState();

      case 'query_time_date':
        return this.queryTimeDate();

      case 'list_files':
        return this.listFiles(args as { path: string; pattern?: string });

      case 'create_file':
        return this.createFile(args as { path: string; content: string });

      case 'read_file':
        return this.readFile(args as { path: string });

      case 'delete_file':
        return this.deleteFile(args as { path: string });

      case 'move_file':
        return this.moveFile(args as { source: string; destination: string });

      case 'search_files':
        return this.searchFiles(args as { query: string; path?: string });

      case 'manage_window':
        return this.manageWindow(args as { action: string; title: string });

      case 'set_volume':
        return this.setVolume(args as { level: number });

      case 'open_url':
        return this.openUrl(args as { url: string });

      default:
        throw new Error(`Unknown function: ${functionName}`);
    }
  }

  // ==================== Security Utilities ====================

  /**
   * Validate and sanitize a file path to prevent path traversal attacks
   */
  private validatePath(inputPath: string): string {
    // Resolve to absolute path
    const resolvedPath = path.resolve(inputPath);

    // Check if path is within allowed base paths
    const isAllowed = SECURITY_CONFIG.allowedBasePaths.some(basePath => {
      const resolvedBase = path.resolve(basePath);
      return resolvedPath.startsWith(resolvedBase);
    });

    if (!isAllowed) {
      throw new Error(`Path access denied: ${inputPath} is outside allowed directories`);
    }

    // Check for path traversal attempts
    if (inputPath.includes('..')) {
      const normalized = path.normalize(inputPath);
      if (normalized.includes('..')) {
        throw new Error(`Invalid path: path traversal detected`);
      }
    }

    return resolvedPath;
  }

  /**
   * Validate a command for dangerous patterns
   */
  private validateCommand(command: string): void {
    // Check command length
    if (command.length > SECURITY_CONFIG.maxCommandLength) {
      throw new Error(`Command too long: max ${SECURITY_CONFIG.maxCommandLength} characters`);
    }

    // Check for dangerous patterns
    for (const pattern of SECURITY_CONFIG.dangerousPatterns) {
      if (pattern.test(command)) {
        throw new Error(`Command blocked: contains dangerous pattern`);
      }
    }

    // Check if command starts with allowed prefix (case-insensitive)
    const commandLower = command.toLowerCase().trim();
    const isAllowed = SECURITY_CONFIG.allowedCommandPrefixes.some(prefix =>
      commandLower.startsWith(prefix.toLowerCase())
    );

    if (!isAllowed) {
      logger.warn('Command does not match allowed prefixes', { command });
      throw new Error(`Command not allowed: must start with an allowed command prefix`);
    }
  }

  /**
   * Validate a URL for safe protocols
   */
  private validateUrl(url: string): void {
    try {
      const parsedUrl = new URL(url);

      // Only allow http and https protocols
      if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
        throw new Error(`URL protocol not allowed: ${parsedUrl.protocol}`);
      }

      // Block localhost and private IPs (basic check)
      const hostname = parsedUrl.hostname.toLowerCase();
      const blockedHosts = ['localhost', '127.0.0.1', '0.0.0.0', '::1'];
      if (blockedHosts.includes(hostname)) {
        throw new Error(`URL host not allowed: ${hostname}`);
      }

      // Block private IP ranges (basic check)
      if (/^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)/.test(hostname)) {
        throw new Error(`URL host not allowed: private IP range`);
      }

    } catch (error: any) {
      if (error.message.includes('not allowed')) {
        throw error;
      }
      throw new Error(`Invalid URL: ${url}`);
    }
  }

  /**
   * Sanitize a string for shell use
   */
  private sanitizeForShell(input: string): string {
    // Remove or escape dangerous characters
    return input
      .replace(/[;&|`$(){}[\]<>\\]/g, '')  // Remove shell metacharacters
      .replace(/"/g, '\\"')                  // Escape quotes
      .substring(0, 200);                    // Limit length
  }

  // ==================== Function Implementations ====================

  private async launchApplication(args: { name: string; args?: string[]; cwd?: string }) {
    const { name, args: appArgs = [], cwd } = args;

    // Sanitize app name
    const sanitizedName = this.sanitizeForShell(name);

    // Map common app names to their executables (whitelist approach)
    const appMap: Record<string, string> = {
      chrome: 'chrome.exe',
      firefox: 'firefox.exe',
      edge: 'msedge.exe',
      vscode: 'code.cmd',
      notepad: 'notepad.exe',
      calculator: 'calc.exe',
      explorer: 'explorer.exe',
    };

    const executable = appMap[sanitizedName.toLowerCase()];

    if (!executable) {
      throw new Error(`Application not in allowed list: ${name}. Allowed: ${Object.keys(appMap).join(', ')}`);
    }

    // Validate cwd if provided
    const workingDir = cwd ? this.validatePath(cwd) : process.cwd();

    return new Promise((resolve, reject) => {
      const proc = spawn(executable, appArgs.map(a => this.sanitizeForShell(a)), {
        cwd: workingDir,
        detached: true,
        stdio: 'ignore',
      });

      proc.on('error', (error) => {
        reject(new Error(`Failed to launch ${name}: ${error.message}`));
      });

      proc.unref();
      resolve({ success: true, message: `Launched ${name}` });
    });
  }

  private async openFile(args: { path: string }) {
    const filePath = this.validatePath(args.path);

    // Validate file exists
    try {
      await fs.access(filePath);
    } catch {
      throw new Error(`File not found: ${filePath}`);
    }

    // Use Windows 'start' command to open with default application
    // Escape the path properly
    const escapedPath = filePath.replace(/"/g, '""');
    await execAsync(`start "" "${escapedPath}"`);

    return { success: true, message: `Opened ${filePath}` };
  }

  private async executeCommand(args: { command: string }) {
    const { command } = args;

    // Validate command for security
    this.validateCommand(command);

    // Execute PowerShell command with restricted execution
    const { stdout, stderr } = await execAsync(
      `powershell.exe -NoProfile -ExecutionPolicy Restricted -Command "${command.replace(/"/g, '\\"')}"`,
      { timeout: 30000 } // 30 second timeout
    );

    return {
      success: true,
      stdout: stdout.trim().substring(0, 5000), // Limit output
      stderr: stderr.trim().substring(0, 1000),
    };
  }

  private async querySystemState() {
    const cpus = os.cpus();
    const totalMem = os.totalmem();
    const freeMem = os.freemem();

    const cpuUsage = cpus.reduce((acc, cpu) => {
      const total = Object.values(cpu.times).reduce((a, b) => a + b, 0);
      const idle = cpu.times.idle;
      return acc + (1 - idle / total) * 100;
    }, 0) / cpus.length;

    const memoryUsage = ((totalMem - freeMem) / totalMem) * 100;

    // Get running processes (simplified)
    try {
      const { stdout } = await execAsync('tasklist /FO CSV /NH', { timeout: 10000 });
      const processes = stdout.split('\n').slice(0, 10).map(line => {
        const parts = line.split(',');
        return {
          name: parts[0]?.replace(/"/g, ''),
          pid: parts[1]?.replace(/"/g, ''),
        };
      });

      return {
        cpu: cpuUsage.toFixed(1) + '%',
        memory: memoryUsage.toFixed(1) + '%',
        totalMemory: (totalMem / 1024 / 1024 / 1024).toFixed(2) + ' GB',
        freeMemory: (freeMem / 1024 / 1024 / 1024).toFixed(2) + ' GB',
        uptime: (os.uptime() / 3600).toFixed(1) + ' hours',
        processes: processes.filter(p => p.name),
      };
    } catch {
      return {
        cpu: cpuUsage.toFixed(1) + '%',
        memory: memoryUsage.toFixed(1) + '%',
        totalMemory: (totalMem / 1024 / 1024 / 1024).toFixed(2) + ' GB',
        freeMemory: (freeMem / 1024 / 1024 / 1024).toFixed(2) + ' GB',
        uptime: (os.uptime() / 3600).toFixed(1) + ' hours',
      };
    }
  }

  private queryTimeDate() {
    const now = new Date();
    return {
      date: now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }),
      time: now.toLocaleTimeString('en-US'),
      timestamp: now.toISOString(),
    };
  }

  private async listFiles(args: { path: string; pattern?: string }) {
    const dirPath = this.validatePath(args.path);
    const { pattern } = args;

    const files = await fs.readdir(dirPath);

    const filteredFiles = pattern
      ? files.filter(f => f.includes(pattern.replace(/[*?]/g, '')))
      : files;

    const fileDetails = await Promise.all(
      filteredFiles.slice(0, 50).map(async (file) => {
        const filePath = path.join(dirPath, file);
        try {
          const stats = await fs.stat(filePath);
          return {
            name: file,
            size: stats.size,
            isDirectory: stats.isDirectory(),
            modified: stats.mtime.toISOString(),
          };
        } catch {
          return {
            name: file,
            size: 0,
            isDirectory: false,
            modified: '',
            error: 'Could not read file info',
          };
        }
      })
    );

    return {
      path: dirPath,
      count: fileDetails.length,
      files: fileDetails,
    };
  }

  private async createFile(args: { path: string; content: string }) {
    const filePath = this.validatePath(args.path);
    const { content } = args;

    // Limit content size
    if (content.length > SECURITY_CONFIG.maxFileSize) {
      throw new Error(`Content too large: max ${SECURITY_CONFIG.maxFileSize} bytes`);
    }

    await fs.writeFile(filePath, content, 'utf-8');

    return { success: true, message: `Created ${filePath}` };
  }

  private async readFile(args: { path: string }) {
    const filePath = this.validatePath(args.path);

    // Check file size before reading
    const stats = await fs.stat(filePath);
    if (stats.size > SECURITY_CONFIG.maxFileSize) {
      throw new Error(`File too large: max ${SECURITY_CONFIG.maxFileSize} bytes`);
    }

    const content = await fs.readFile(filePath, 'utf-8');

    // Limit content length for response
    const truncated = content.length > 1000 ? content.substring(0, 1000) + '...' : content;

    return {
      path: filePath,
      size: content.length,
      content: truncated,
    };
  }

  private async deleteFile(args: { path: string }) {
    const filePath = this.validatePath(args.path);

    // Check it's a file not a directory
    const stats = await fs.stat(filePath);
    if (stats.isDirectory()) {
      throw new Error(`Cannot delete directory with this function: ${filePath}`);
    }

    await fs.unlink(filePath);

    return { success: true, message: `Deleted ${filePath}` };
  }

  private async moveFile(args: { source: string; destination: string }) {
    const sourcePath = this.validatePath(args.source);
    const destPath = this.validatePath(args.destination);

    await fs.rename(sourcePath, destPath);

    return { success: true, message: `Moved ${sourcePath} to ${destPath}` };
  }

  private async searchFiles(args: { query: string; path?: string }) {
    const searchPath = this.validatePath(args.path || process.cwd());
    const query = args.query.substring(0, 100); // Limit query length

    const files = await fs.readdir(searchPath);
    const matches = files.filter(f => f.toLowerCase().includes(query.toLowerCase()));

    return {
      query,
      path: searchPath,
      matches: matches.slice(0, 20),
    };
  }

  private async manageWindow(args: { action: string; title: string }) {
    const { action } = args;
    const title = this.sanitizeForShell(args.title);

    // Validate action
    const allowedActions = ['minimize', 'maximize', 'close', 'focus'];
    if (!allowedActions.includes(action)) {
      throw new Error(`Invalid action: ${action}. Allowed: ${allowedActions.join(', ')}`);
    }

    // Use PowerShell to manage windows
    let command = '';

    switch (action) {
      case 'minimize':
        command = `$w = Get-Process | Where-Object {$_.MainWindowTitle -like "*${title}*"}; if($w){$w | ForEach-Object {(New-Object -ComObject Shell.Application).MinimizeAll()}}`;
        break;
      case 'maximize':
        command = `$w = Get-Process | Where-Object {$_.MainWindowTitle -like "*${title}*"}; if($w){Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("% x")}`;
        break;
      case 'close':
        command = `Get-Process | Where-Object {$_.MainWindowTitle -like "*${title}*"} | Stop-Process`;
        break;
      case 'focus':
        command = `$w = Get-Process | Where-Object {$_.MainWindowTitle -like "*${title}*"}; if($w){Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.Interaction]::AppActivate($w.Id)}`;
        break;
    }

    await execAsync(`powershell.exe -NoProfile -Command "${command}"`, { timeout: 10000 });

    return { success: true, message: `${action} window: ${title}` };
  }

  private async setVolume(args: { level: number }) {
    const { level } = args;

    // Clamp level between 0-100
    const clampedLevel = Math.max(0, Math.min(100, Math.floor(level)));

    // Use PowerShell to set volume
    const command = `(New-Object -ComObject WScript.Shell).SendKeys([char]174); Start-Sleep -Milliseconds 100; $obj = New-Object -ComObject WScript.Shell; for($i=0; $i -lt 50; $i++){$obj.SendKeys([char]174)}; for($i=0; $i -lt ${Math.floor(clampedLevel / 2)}; $i++){$obj.SendKeys([char]175)}`;

    await execAsync(`powershell.exe -NoProfile -Command "${command}"`, { timeout: 15000 });

    return { success: true, message: `Set volume to ${clampedLevel}%` };
  }

  private async openUrl(args: { url: string }) {
    const { url } = args;

    // Validate URL for security
    this.validateUrl(url);

    // Use start command with the validated URL
    await execAsync(`start "" "${url.replace(/"/g, '')}"`);

    return { success: true, message: `Opened ${url}` };
  }
}
