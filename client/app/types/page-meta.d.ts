declare module '#app' {
  interface PageMeta {
    /**
     * Who may open the page:
     * - `guest` — only visitors who are not logged in
     * - `auth` — logged in users (default)
     * - `setup` — logged in users and tutors/admins who must enable 2FA first
     * - `public` — everyone
     */
    access?: 'guest' | 'auth' | 'setup' | 'public'
  }
}

// oxlint-disable-next-line unicorn/require-module-specifiers -- makes this file a module
export {}
