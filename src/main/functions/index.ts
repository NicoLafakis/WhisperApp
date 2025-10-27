/**
 * JARVIS Voice Agent - Function Definitions
 * All available system functions for Windows integration
 */

import { FunctionDefinition } from '../../shared/types';

export const JARVIS_FUNCTIONS: FunctionDefinition[] = [
  {
    name: 'launch_application',
    description: 'Launch an application on Windows',
    parameters: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'The application name (e.g., "chrome", "vscode", "notepad")',
        },
        args: {
          type: 'array',
          items: { type: 'string' },
          description: 'Optional command line arguments',
        },
        cwd: {
          type: 'string',
          description: 'Optional working directory',
        },
      },
      required: ['name'],
    },
  },
  {
    name: 'open_file',
    description: 'Open a file with its default application',
    parameters: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'The file path to open',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'execute_command',
    description: 'Execute a PowerShell command',
    parameters: {
      type: 'object',
      properties: {
        command: {
          type: 'string',
          description: 'The PowerShell command to execute',
        },
      },
      required: ['command'],
    },
  },
  {
    name: 'query_system_state',
    description: 'Get current system information (CPU, memory, processes)',
    parameters: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'query_time_date',
    description: 'Get the current time and date',
    parameters: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'list_files',
    description: 'List files in a directory',
    parameters: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'The directory path',
        },
        pattern: {
          type: 'string',
          description: 'Optional file pattern (e.g., "*.pdf")',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'create_file',
    description: 'Create a new file with content',
    parameters: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'The file path',
        },
        content: {
          type: 'string',
          description: 'The file content',
        },
      },
      required: ['path', 'content'],
    },
  },
  {
    name: 'read_file',
    description: 'Read the contents of a file',
    parameters: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'The file path',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'delete_file',
    description: 'Delete a file (requires confirmation)',
    parameters: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'The file path',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'move_file',
    description: 'Move or rename a file',
    parameters: {
      type: 'object',
      properties: {
        source: {
          type: 'string',
          description: 'The source file path',
        },
        destination: {
          type: 'string',
          description: 'The destination file path',
        },
      },
      required: ['source', 'destination'],
    },
  },
  {
    name: 'search_files',
    description: 'Search for files matching a pattern',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query or pattern',
        },
        path: {
          type: 'string',
          description: 'Directory to search in',
        },
      },
      required: ['query'],
    },
  },
  {
    name: 'manage_window',
    description: 'Manage application window (minimize, maximize, close)',
    parameters: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          enum: ['minimize', 'maximize', 'close', 'focus'],
          description: 'The window action to perform',
        },
        title: {
          type: 'string',
          description: 'The window title or partial match',
        },
      },
      required: ['action', 'title'],
    },
  },
  {
    name: 'set_volume',
    description: 'Set the system volume',
    parameters: {
      type: 'object',
      properties: {
        level: {
          type: 'number',
          description: 'Volume level (0-100)',
        },
      },
      required: ['level'],
    },
  },
  {
    name: 'open_url',
    description: 'Open a URL in the default browser',
    parameters: {
      type: 'object',
      properties: {
        url: {
          type: 'string',
          description: 'The URL to open',
        },
      },
      required: ['url'],
    },
  },
];
