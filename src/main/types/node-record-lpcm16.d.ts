/**
 * JARVIS Voice Agent - Type Definitions for node-record-lpcm16
 * TypeScript declaration for the node-record-lpcm16 audio recording library
 */

declare module 'node-record-lpcm16' {
  import { Readable } from 'stream';

  interface RecordingOptions {
    sampleRate?: number;
    channels?: number;
    threshold?: number;
    endOnSilence?: boolean;
    silence?: string;
    recorder?: string;
    device?: string;
    audioType?: string;
  }

  interface Recording {
    stream(): Readable;
    stop(): void;
    pause(): void;
    resume(): void;
  }

  export function record(options?: RecordingOptions): Recording;
  export function stop(): void;
}
