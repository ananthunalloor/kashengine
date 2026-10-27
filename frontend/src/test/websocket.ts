/** A WebSocket stand-in for tests: records sent frames and lets a test push server events. */
export class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSING = 2;
  readonly CLOSED = 3;
  readyState = 0;
  sent: unknown[] = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  readonly url: string;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  static get latest() {
    return MockWebSocket.instances[MockWebSocket.instances.length - 1];
  }

  send(data: string) {
    this.sent.push(JSON.parse(data));
  }

  close(code = 1000) {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.onclose?.({ code } as CloseEvent);
  }

  open() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  receive(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }

  serverClose(code: number) {
    this.readyState = 3;
    this.onclose?.({ code } as CloseEvent);
  }
}
