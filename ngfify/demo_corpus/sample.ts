/**
 * Tiny demo module for ngfify's TypeScript deriver.
 */

import { readFileSync } from "node:fs";
import type { Options } from "./options";

export interface Greeting {
  message: string;
}

export function greet(name: string): Greeting {
  return { message: `Hello, ${name}!` };
}

export const DEFAULT_NAME = "world";

function internalHelper(): void {
  // not exported -- must never appear in public_interfaces
}

export { internalHelperAlias as helperAlias } from "./helpers";

export default class GreeterService {
  greet(name: string): Greeting {
    return greet(name);
  }
}
