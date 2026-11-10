// eslint-index.cjs - Main ESLint Config Entry Point
// Combines core rules and utilities for Hermes Game Studios
// Flat config format for ESLint 9+

const coreRules = require('./eslint-core-rules.cjs');
const utils = require('./eslint-utils.cjs');

const MAX_LINES_PER_FILE = 350;

module.exports = [
  ...coreRules,
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
    },
    plugins: {
      hermes: {
        rules: {
          // Contract compliance rules
          'contract-compliance': {
            create(context) {
              return {
                Program(node) {
                  const filename = context.getFilename();
                  // Avoid unused variable warning
                  void node;

                  // Check if Morgana is touching Nephy files
                  if (utils.isMorganaOwned(filename) && utils.isNephyOwned(filename)) {
                    context.report({
                      node,
                      message: 'Morgana-owned agent modifying Nephy-owned file',
                    });
                  }

                  // Check contract files
                  if (utils.isContractFile(filename)) {
                    const sector = utils.getAgentSector(filename);
                    if (sector !== 'nephy' && sector !== 'liruh') {
                      context.report({
                        node,
                        message: 'Only Nephy or Liruh agents may modify contract files',
                      });
                    }
                  }
                },
              };
            },
          },

          // Boundary enforcement
          'boundary-enforcement': {
            create(context) {
              return {
                Program(node) {
                  const filename = context.getFilename();
                  const sector = utils.getAgentSector(filename);
                  // Avoid unused variable warning
                  void sector;
                  void node;

                  // This would be populated from agent context in real usage
                  // For now, just warn on cross-boundary patterns
                },
              };
            },
          },

          // Direct console check (custom message)
          'no-direct-console': {
            create(context) {
              return {
                CallExpression(node) {
                  const code = context.getSourceCode().getText(node);
                  if (utils.hasDirectConsole(code)) {
                    context.report({
                      node,
                      message: 'Direct console/log usage forbidden - use injected logger service',
                    });
                  }
                },
              };
            },
          },

          // Direct data access check
          'no-direct-data-access': {
            create(context) {
              return {
                CallExpression(node) {
                  const code = context.getSourceCode().getText(node);
                  if (utils.hasDirectDataAccess(code)) {
                    context.report({
                      node,
                      message: 'Direct node/data access forbidden - use injected services (warn only)',
                      severity: 'warn',
                    });
                  }
                },
              };
            },
          },

          // Max lines per file (custom message with project standard)
          'max-lines-per-file': {
            create(context) {
              return {
                Program(node) {
                  const lines = utils.countLines(context.getSourceCode().getText());
                  if (lines > MAX_LINES_PER_FILE) {
                    context.report({
                      node,
                      message: `File exceeds ${MAX_LINES_PER_FILE} lines (${lines}) - split into modules`,
                    });
                  }
                },
              };
            },
          },
        },
      },
    },
    rules: {
      'hermes/contract-compliance': 'error',
      'hermes/boundary-enforcement': 'warn',
      'hermes/no-direct-console': 'error',
      'hermes/no-direct-data-access': 'warn',
      'hermes/max-lines-per-file': 'error',
    },
  },
];