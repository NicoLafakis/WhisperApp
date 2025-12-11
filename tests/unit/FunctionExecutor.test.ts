/**
 * Unit tests for FunctionExecutor
 */

import { FunctionExecutor, ConfirmationCallback } from '../../src/main/functions/executor';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as os from 'os';

// Mock child_process to avoid actual command execution in tests
jest.mock('child_process', () => ({
  exec: jest.fn((cmd, options, callback) => {
    // Handle both (cmd, callback) and (cmd, options, callback) signatures
    const cb = typeof options === 'function' ? options : callback;
    if (typeof cb === 'function') {
      cb(null, { stdout: 'mocked output', stderr: '' });
    }
    return { on: jest.fn() };
  }),
  spawn: jest.fn(() => ({
    on: jest.fn((event, callback) => {
      if (event === 'error') return;
    }),
    unref: jest.fn(),
  })),
}));

jest.mock('util', () => ({
  ...jest.requireActual('util'),
  promisify: jest.fn((fn) => {
    return async (...args: any[]) => {
      return { stdout: 'mocked output', stderr: '' };
    };
  }),
}));

describe('FunctionExecutor', () => {
  let executor: FunctionExecutor;
  let executorWithConfirmation: FunctionExecutor;
  const mockConfirmationCallback: ConfirmationCallback = jest.fn().mockResolvedValue(true);

  beforeEach(() => {
    executor = new FunctionExecutor(
      ['access_credentials', 'modify_admin_protected'], // blocked functions
      [] // No confirmation required for basic tests
    );

    // Executor that requires confirmation for destructive operations
    executorWithConfirmation = new FunctionExecutor(
      ['access_credentials'],
      ['delete_file', 'execute_command', 'move_file']
    );
    executorWithConfirmation.setConfirmationCallback(mockConfirmationCallback);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('constructor', () => {
    it('should initialize with blocked functions', () => {
      const exec = new FunctionExecutor(['func1', 'func2'], []);
      expect(exec).toBeDefined();
    });

    it('should initialize with confirmation-required functions', () => {
      const exec = new FunctionExecutor([], ['func1', 'func2']);
      expect(exec).toBeDefined();
    });

    it('should work with empty arrays', () => {
      const exec = new FunctionExecutor([], []);
      expect(exec).toBeDefined();
    });
  });

  describe('execute', () => {
    it('should throw error for blocked functions', async () => {
      await expect(
        executor.execute('access_credentials', {})
      ).rejects.toThrow('blocked for security reasons');
    });

    it('should throw error for unknown functions', async () => {
      await expect(
        executor.execute('unknown_function', {})
      ).rejects.toThrow('Unknown function');
    });
  });

  describe('confirmation mechanism', () => {
    it('should call confirmation callback for protected functions', async () => {
      const testDir = path.join(os.tmpdir(), 'jarvis-confirm-test');
      const testFile = path.join(testDir, 'confirm-delete.txt');

      await fs.mkdir(testDir, { recursive: true });
      await fs.writeFile(testFile, 'test');

      await executorWithConfirmation.execute('delete_file', { path: testFile });

      expect(mockConfirmationCallback).toHaveBeenCalledWith(
        'delete_file',
        { path: testFile },
        expect.stringContaining('Delete file')
      );

      // Cleanup
      try {
        await fs.rm(testDir, { recursive: true });
      } catch {}
    });

    it('should deny action when no confirmation callback is set', async () => {
      const noCallbackExecutor = new FunctionExecutor([], ['delete_file']);
      const testFile = path.join(os.tmpdir(), 'test-no-callback.txt');
      await fs.writeFile(testFile, 'test');

      await expect(
        noCallbackExecutor.execute('delete_file', { path: testFile })
      ).rejects.toThrow('was not approved by user');

      // File should still exist
      await expect(fs.access(testFile)).resolves.toBeUndefined();

      // Cleanup
      await fs.unlink(testFile);
    });

    it('should deny action when confirmation callback returns false', async () => {
      const denyCallback: ConfirmationCallback = jest.fn().mockResolvedValue(false);
      const denyExecutor = new FunctionExecutor([], ['delete_file']);
      denyExecutor.setConfirmationCallback(denyCallback);

      const testFile = path.join(os.tmpdir(), 'test-deny.txt');
      await fs.writeFile(testFile, 'test');

      await expect(
        denyExecutor.execute('delete_file', { path: testFile })
      ).rejects.toThrow('was not approved by user');

      // Cleanup
      await fs.unlink(testFile);
    });
  });

  describe('queryTimeDate', () => {
    it('should return current date and time', async () => {
      const result = await executor.execute('query_time_date', {});

      expect(result).toHaveProperty('date');
      expect(result).toHaveProperty('time');
      expect(result).toHaveProperty('timestamp');
      expect(result.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    });
  });

  describe('querySystemState', () => {
    it('should return system metrics', async () => {
      const result = await executor.execute('query_system_state', {});

      expect(result).toHaveProperty('cpu');
      expect(result).toHaveProperty('memory');
      expect(result).toHaveProperty('totalMemory');
      expect(result).toHaveProperty('freeMemory');
      expect(result).toHaveProperty('uptime');
    });
  });

  describe('file operations', () => {
    const testDir = path.join(os.tmpdir(), 'jarvis-test');
    const testFile = path.join(testDir, 'test.txt');

    beforeAll(async () => {
      await fs.mkdir(testDir, { recursive: true });
    });

    afterAll(async () => {
      try {
        await fs.rm(testDir, { recursive: true });
      } catch {
        // Ignore cleanup errors
      }
    });

    describe('createFile', () => {
      it('should create a file with content', async () => {
        const result = await executor.execute('create_file', {
          path: testFile,
          content: 'Hello, JARVIS!',
        });

        expect(result.success).toBe(true);

        const content = await fs.readFile(testFile, 'utf-8');
        expect(content).toBe('Hello, JARVIS!');
      });
    });

    describe('readFile', () => {
      beforeEach(async () => {
        await fs.writeFile(testFile, 'Test content');
      });

      it('should read file content', async () => {
        const result = await executor.execute('read_file', {
          path: testFile,
        });

        expect(result.content).toBe('Test content');
      });

      it('should truncate long content', async () => {
        const longContent = 'x'.repeat(2000);
        await fs.writeFile(testFile, longContent);

        const result = await executor.execute('read_file', {
          path: testFile,
        });

        expect(result.content.length).toBeLessThanOrEqual(1003); // 1000 + '...'
      });
    });

    describe('listFiles', () => {
      beforeEach(async () => {
        await fs.writeFile(path.join(testDir, 'file1.txt'), 'content1');
        await fs.writeFile(path.join(testDir, 'file2.txt'), 'content2');
      });

      it('should list files in directory', async () => {
        const result = await executor.execute('list_files', {
          path: testDir,
        });

        expect(result.files).toBeDefined();
        expect(result.files.length).toBeGreaterThan(0);
      });

      it('should filter files by pattern', async () => {
        const result = await executor.execute('list_files', {
          path: testDir,
          pattern: '.txt',
        });

        expect(result.files.every((f: any) => f.name.includes('.txt'))).toBe(true);
      });
    });

    describe('searchFiles', () => {
      beforeEach(async () => {
        await fs.writeFile(path.join(testDir, 'search-test.txt'), 'content');
      });

      it('should search for files by query', async () => {
        const result = await executor.execute('search_files', {
          query: 'search',
          path: testDir,
        });

        expect(result.matches).toBeDefined();
        expect(result.matches.some((f: string) => f.includes('search'))).toBe(true);
      });
    });

    describe('deleteFile', () => {
      it('should delete a file when confirmed', async () => {
        const fileToDelete = path.join(testDir, 'delete-me.txt');
        await fs.writeFile(fileToDelete, 'delete me');

        // Use executor with confirmation callback that approves
        const result = await executorWithConfirmation.execute('delete_file', {
          path: fileToDelete,
        });

        expect(result.success).toBe(true);
        await expect(fs.access(fileToDelete)).rejects.toThrow();
      });
    });

    describe('moveFile', () => {
      it('should move a file when confirmed', async () => {
        const source = path.join(testDir, 'move-source.txt');
        const dest = path.join(testDir, 'move-dest.txt');
        await fs.writeFile(source, 'move me');

        const result = await executorWithConfirmation.execute('move_file', {
          source,
          destination: dest,
        });

        expect(result.success).toBe(true);

        await expect(fs.access(source)).rejects.toThrow();
        const content = await fs.readFile(dest, 'utf-8');
        expect(content).toBe('move me');
      });
    });
  });

  describe('security - path validation', () => {
    it('should block path traversal attempts', async () => {
      await expect(
        executor.execute('read_file', { path: '/etc/passwd' })
      ).rejects.toThrow('outside allowed directories');
    });

    it('should allow paths within allowed directories', async () => {
      const validPath = path.join(os.tmpdir(), 'valid-test.txt');
      await fs.writeFile(validPath, 'valid content');

      const result = await executor.execute('read_file', { path: validPath });

      expect(result.content).toBe('valid content');

      // Cleanup
      await fs.unlink(validPath);
    });
  });

  describe('security - URL validation', () => {
    it('should block non-http protocols', async () => {
      await expect(
        executor.execute('open_url', { url: 'file:///etc/passwd' })
      ).rejects.toThrow('protocol not allowed');
    });

    it('should block localhost URLs', async () => {
      await expect(
        executor.execute('open_url', { url: 'http://localhost:8080' })
      ).rejects.toThrow('host not allowed');
    });

    it('should block private IP ranges', async () => {
      await expect(
        executor.execute('open_url', { url: 'http://192.168.1.1' })
      ).rejects.toThrow('host not allowed');
    });

    it('should allow valid https URLs', async () => {
      // This will be mocked, so it won't actually open a URL
      const result = await executor.execute('open_url', { url: 'https://www.example.com' });
      expect(result.success).toBe(true);
    });
  });

  describe('security - command validation', () => {
    it('should block dangerous command patterns', async () => {
      const dangerousExecutor = new FunctionExecutor([], []);

      // These should all be blocked by pattern matching or prefix whitelist
      await expect(
        dangerousExecutor.execute('execute_command', { command: 'rm -rf /' })
      ).rejects.toThrow();
    });

    it('should only allow whitelisted command prefixes', async () => {
      const cmdExecutor = new FunctionExecutor([], []);

      // Allowed command (starts with Get-)
      // Note: Will still fail due to mock, but won't fail security check
      await expect(
        cmdExecutor.execute('execute_command', { command: 'Get-Process' })
      ).resolves.toBeDefined();
    });

    it('should block commands that exceed max length', async () => {
      const longCommand = 'Get-' + 'x'.repeat(600);

      await expect(
        executor.execute('execute_command', { command: longCommand })
      ).rejects.toThrow('Command too long');
    });
  });

  describe('security - application whitelist', () => {
    it('should only allow whitelisted applications', async () => {
      await expect(
        executor.execute('launch_application', { name: 'malicious.exe' })
      ).rejects.toThrow('not in allowed list');
    });

    it('should allow whitelisted applications', async () => {
      // This will fail due to spawn mock, but won't fail security check
      const result = await executor.execute('launch_application', { name: 'notepad' });
      expect(result.success).toBe(true);
    });
  });

  describe('security - blocked functions', () => {
    it('should block dangerous functions', async () => {
      const blockedExecutor = new FunctionExecutor(
        ['execute_command', 'delete_file'],
        []
      );

      await expect(
        blockedExecutor.execute('execute_command', { command: 'Get-Process' })
      ).rejects.toThrow('blocked for security reasons');
    });
  });
});
