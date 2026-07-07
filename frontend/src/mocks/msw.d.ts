/**
 * Ambient type declarations for MSW v2.
 * The installed version is missing compiled .d.ts files; these stubs provide
 * the minimal surface used by the LBRO mock handlers so TypeScript is happy.
 */

declare module 'msw' {
  export type PathParams = Record<string, string | string[]>

  export interface ResolverInfo {
    request: Request
    params: PathParams
    cookies: Record<string, string>
  }

  export type Resolver = (
    info: ResolverInfo,
  ) => Response | Promise<Response> | void | Promise<void>

  export type RequestHandler = unknown

  export const http: {
    get(path: string, resolver: Resolver): RequestHandler
    post(path: string, resolver: Resolver): RequestHandler
    put(path: string, resolver: Resolver): RequestHandler
    patch(path: string, resolver: Resolver): RequestHandler
    delete(path: string, resolver: Resolver): RequestHandler
    all(path: string, resolver: Resolver): RequestHandler
  }

  export const HttpResponse: {
    json<T = unknown>(body: T, init?: ResponseInit): Response
    text(body: string, init?: ResponseInit): Response
    new (body?: BodyInit | null, init?: ResponseInit): Response
  }

  export function delay(ms?: number): Promise<void>
}

declare module 'msw/browser' {
  import type { RequestHandler } from 'msw'

  export interface SetupWorker {
    start(options?: {
      onUnhandledRequest?: 'warn' | 'error' | 'bypass'
      serviceWorker?: { url?: string }
    }): Promise<void>
    stop(): void
  }

  export function setupWorker(...handlers: RequestHandler[]): SetupWorker
}
