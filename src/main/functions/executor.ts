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

export class FunctionExecutor {
  private blockedFunctions: Set<string> = new Set();
  private confirmationRequired: Set<string> = new Set();

  constructor(blockedFunctions: string[] = [], confirmationRequired: string[] = []) {
    this.blockedFunctions = new Set(blockedFunctions);
    this.confirmationRequired = new Set(confirmationRequired);
  }

  async execute(functionName: string, args: Record<string, any>): Promise<any> {
    logger.info('Executing function', { functionName, args });

    // Check if function is blocked
    if (this.blockedFunctions.has(functionName)) {
      throw new Error(`Function ${functionName} is blocked for security reasons`);
    }

    // Check if confirmation is required (in production, this would prompt the user)
    if (this.confirmationRequired.has(functionName)) {
      logger.warn('Function requires confirmation', { functionName });
      // TODO: Implement user confirmation mechanism
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

  private async executeFunction(functionName: string, args: Record<string, any>): Promise<any> {
    switch (functionName) {
      case 'launch_application':
        return this.launchApplication(args);

      case 'open_file':
        return this.openFile(args);

      case 'execute_command':
        return this.executeCommand(args);

      case 'query_system_state':
        return this.querySystemState();

      case 'query_time_date':
        return this.queryTimeDate();

      case 'list_files':
        return this.listFiles(args);

      case 'create_file':
        return this.createFile(args);

      case 'read_file':
        return this.readFile(args);

      case 'delete_file':
        return this.deleteFile(args);

      case 'move_file':
        return this.moveFile(args);

      case 'search_files':
        return this.searchFiles(args);

      case 'manage_window':
        return this.manageWindow(args);

      case 'set_volume':
        return this.setVolume(args);

      case 'open_url':
        return this.openUrl(args);

      default:
        throw new Error(`Unknown function: ${functionName}`);
    }
  }

  // ==================== Function Implementations ====================

  private async launchApplication(args: { name: string; args?: string[]; cwd?: string }) {
    const { name, args: appArgs = [], cwd } = args;

    // Map common app names to their executables
    const appMap: Record<string, string> = {
      chrome: 'chrome.exe',
      firefox: 'firefox.exe',
      edge: 'msedge.exe',
      vscode: 'code.cmd',
      notepad: 'notepad.exe',
      calculator: 'calc.exe',
      explorer: 'explorer.exe',
      cmd: 'cmd.exe',
      powershell: 'powershell.exe',
    };

    const executable = appMap[name.toLowerCase()] || name;

    return new Promise((resolve, reject) => {
      const proc = spawn(executable, appArgs, {
        cwd: cwd || process.cwd(),
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
    const filePath = args.path;

    // Validate file exists
    try {
      await fs.access(filePath);
    } catch {
      throw new Error(`File not found: ${filePath}`);
    }

    // Use Windows 'start' command to open with default application
    await execAsync(`start "" "${filePath}"`);

    return { success: true, message: `Opened ${filePath}` };
  }

  private async executeCommand(args: { command: string }) {
    const { command } = args;

    // Execute PowerShell command
    const { stdout, stderr } = await execAsync(`powershell.exe -Command "${command}"`);

    return {
      success: true,
      stdout: stdout.trim(),
      stderr: stderr.trim(),
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
      const { stdout } = await execAsync('tasklist /FO CSV /NH');
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
    const { path: dirPath, pattern } = args;

    const files = await fs.readdir(dirPath);

    const filteredFiles = pattern
      ? files.filter(f => f.includes(pattern.replace('*', '')))
      : files;

    const fileDetails = await Promise.all(
      filteredFiles.slice(0, 50).map(async (file) => {
        const filePath = path.join(dirPath, file);
        const stats = await fs.stat(filePath);
        return {
          name: file,
          size: stats.size,
          isDirectory: stats.isDirectory(),
          modified: stats.mtime.toISOString(),
        };
      })
    );

    return {
      path: dirPath,
      count: fileDetails.length,
      files: fileDetails,
    };
  }

  private async createFile(args: { path: string; content: string }) {
    const { path: filePath, content } = args;

    await fs.writeFile(filePath, content, 'utf-8');

    return { success: true, message: `Created ${filePath}` };
  }

  private async readFile(args: { path: string }) {
    const { path: filePath } = args;

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
    const { path: filePath } = args;

    await fs.unlink(filePath);

    return { success: true, message: `Deleted ${filePath}` };
  }

  private async moveFile(args: { source: string; destination: string }) {
    const { source, destination } = args;

    await fs.rename(source, destination);

    return { success: true, message: `Moved ${source} to ${destination}` };
  }

  private async searchFiles(args: { query: string; path?: string }) {
    const { query, path: searchPath = process.cwd() } = args;

    const files = await fs.readdir(searchPath);
    const matches = files.filter(f => f.toLowerCase().includes(query.toLowerCase()));

    return {
      query,
      path: searchPath,
      matches: matches.slice(0, 20),
    };
  }

  private async manageWindow(args: { action: string; title: string }) {
    const { action, title } = args;

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

    await execAsync(`powershell.exe -Command "${command}"`);

    return { success: true, message: `${action} window: ${title}` };
  }

  private async setVolume(args: { level: number }) {
    const { level } = args;

    // Clamp level between 0-100
    const clampedLevel = Math.max(0, Math.min(100, level));

    // Use PowerShell to set volume
    const command = `(New-Object -ComObject WScript.Shell).SendKeys([char]174); Start-Sleep -Milliseconds 100; $obj = New-Object -ComObject WScript.Shell; for($i=0; $i -lt 50; $i++){$obj.SendKeys([char]174)}; for($i=0; $i -lt ${Math.floor(clampedLevel / 2)}; $i++){$obj.SendKeys([char]175)}`;

    await execAsync(`powershell.exe -Command "${command}"`);

    return { success: true, message: `Set volume to ${clampedLevel}%` };
  }

  private async openUrl(args: { url: string }) {
    const { url } = args;

    await execAsync(`start "" "${url}"`);

    return { success: true, message: `Opened ${url}` };
  }
}
