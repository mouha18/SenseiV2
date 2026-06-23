/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as auth from "../auth.js";
import type * as chat_internal from "../chat_internal.js";
import type * as crons from "../crons.js";
import type * as documents from "../documents.js";
import type * as documents_internal from "../documents_internal.js";
import type * as feynmanScores from "../feynmanScores.js";
import type * as feynman_internal from "../feynman_internal.js";
import type * as http from "../http.js";
import type * as messages from "../messages.js";
import type * as sessions from "../sessions.js";
import type * as sessions_internal from "../sessions_internal.js";
import type * as users from "../users.js";
import type * as users_internal from "../users_internal.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  auth: typeof auth;
  chat_internal: typeof chat_internal;
  crons: typeof crons;
  documents: typeof documents;
  documents_internal: typeof documents_internal;
  feynmanScores: typeof feynmanScores;
  feynman_internal: typeof feynman_internal;
  http: typeof http;
  messages: typeof messages;
  sessions: typeof sessions;
  sessions_internal: typeof sessions_internal;
  users: typeof users;
  users_internal: typeof users_internal;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};
