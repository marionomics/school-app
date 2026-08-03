import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    // Generated shadcn primitives. They export variant objects alongside their
    // components, which trips the hot-reload rule. These files are used exactly
    // as the preset ships them and are never hand-edited, so the exemption goes
    // here rather than into the files.
    files: ['src/components/ui/**/*.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])
