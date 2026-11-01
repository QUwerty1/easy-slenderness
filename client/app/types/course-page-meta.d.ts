import type { Role } from '~/types/auth'

declare module '#app' {
  interface PageMeta {
    /** Roles that may open the page (checked by the `course-role` middleware). */
    roles?: Role[]
  }
}

// oxlint-disable-next-line unicorn/require-module-specifiers -- makes this file a module
export {}
