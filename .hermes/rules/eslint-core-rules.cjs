// eslint-core-rules.cjs - Core ESLint Rules for Hermes Game Studios
// Used by hermes-code-review, validate-commit hook
// Flat config format for ESLint 9+

module.exports = [
  {
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/build/**',
      '**/.hermes/**',
      '**/coverage/**',
      '**/*.min.js',
    ],
  },
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        console: 'readonly',
        process: 'readonly',
        Buffer: 'readonly',
        __dirname: 'readonly',
        __filename: 'readonly',
        module: 'readonly',
        require: 'readonly',
        exports: 'readonly',
        global: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        Promise: 'readonly',
        Error: 'readonly',
        Date: 'readonly',
        Array: 'readonly',
        Object: 'readonly',
        String: 'readonly',
        Number: 'readonly',
        Map: 'readonly',
        Set: 'readonly',
        JSON: 'readonly',
        Math: 'readonly',
        Reflect: 'readonly',
        Symbol: 'readonly',
      },
    },
    rules: {
      // Code Quality
      'no-console': 'error',
      'no-debugger': 'error',
      'no-alert': 'error',
      'no-unused-vars': ['error', { 'argsIgnorePattern': '^_' }],
      'no-undef': 'error',
      'no-unreachable': 'error',
      'no-constant-condition': 'warn',

      // Style
      'indent': ['error', 2],
      'linebreak-style': ['error', 'unix'],
      'quotes': ['error', 'single', { 'avoidEscape': true }],
      'semi': ['error', 'always'],
      'comma-dangle': ['error', 'always-multiline'],
      'object-curly-spacing': ['error', 'always'],
      'array-bracket-spacing': ['error', 'never'],
      'keyword-spacing': ['error', { 'before': true, 'after': true }],
      'space-before-function-paren': ['error', { 'anonymous': 'always', 'named': 'never' }],

      // Best Practices
      'eqeqeq': ['error', 'always'],
      'curly': ['error', 'all'],
      'no-var': 'error',
      'prefer-const': 'error',
      'prefer-arrow-callback': 'error',
      'prefer-template': 'error',
      'no-useless-concat': 'error',

      // Complexity
      'max-lines': ['error', 350],
      'max-lines-per-function': ['error', 50],
      'max-depth': ['error', 4],
      'max-nested-callbacks': ['error', 3],
      'complexity': ['error', 10],

      // Game-specific
      'no-magic-numbers': ['warn', { 'ignore': [0, 1, -1, 2, 3, 4, 5, 10, 100] }],
    },
  },
  {
    files: ['*.gd', '*.gdscript'],
    rules: {
      'no-console': 'off',  // Godot uses print()
      'max-lines': ['error', 350],
    },
  },
  {
    files: ['*.cs'],
    rules: {
      'max-lines': ['error', 350],
    },
  },
  {
    files: ['*.cpp', '*.h'],
    rules: {
      'max-lines': ['error', 350],
    },
  },
];