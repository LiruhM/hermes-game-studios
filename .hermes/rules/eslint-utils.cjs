// eslint-utils.cjs - Utility functions for ESLint rules
// Shared utilities for custom rules

/** 
 * Check if a file is in Morgana's owned territory
 */
function isMorganaOwned(filePath) {
  const morganaPaths = [
    'src/',
    'Assets/',
    'Source/',
    'tests/',
    'tools/',
    'prototypes/',
  ];
  return morganaPaths.some(p => filePath.startsWith(p));
}

/**
 * Check if a file is in Nephy's owned territory
 */
function isNephyOwned(filePath) {
  const nephyPaths = [
    'docs/architecture/',
    'design/gdd/',
    'design/registry/',
    '.hermes/agents/',
    '.hermes/skills/hermes-architecture-',
    '.hermes/skills/hermes-design-',
    'HERMES.md',
    'AGENTS.md',
    'project.yaml',
  ];
  return nephyPaths.some(p => filePath.startsWith(p) || filePath === p);
}

/**
 * Check if file is a contract file
 */
function isContractFile(filePath) {
  return filePath.includes('.hermes/contracts/') && filePath.endsWith('.yaml');
}

/**
 * Get agent sector from file path
 */
function getAgentSector(filePath) {
  if (isNephyOwned(filePath)) { return 'nephy'; }
  if (isMorganaOwned(filePath)) { return 'morgana'; }
  if (filePath.startsWith('production/')) { return 'liruh'; }
  return 'shared';
}

/**
 * Check for direct console/log usage
 */
function hasDirectConsole(code) {
  const patterns = [
    /console\.log\(/,
    /console\.warn\(/,
    /console\.error\(/,
    /print\(/,
    /GD\.print\(/,
    /Debug\.Log\(/,
  ];
  return patterns.some(p => p.test(code));
}

/**
 * Check for direct node/data access
 */
function hasDirectDataAccess(code) {
  const patterns = [
    /get_node\(/,
    /\$[A-Z][a-zA-Z0-9_]*/,
    /Find\(/,
    /GetComponent</,
  ];
  return patterns.some(p => p.test(code));
}

/**
 * Count lines in file
 */
function countLines(content) {
  return content.split('\n').length;
}

module.exports = {
  isMorganaOwned,
  isNephyOwned,
  isContractFile,
  getAgentSector,
  hasDirectConsole,
  hasDirectDataAccess,
  countLines,
};