// ESLint v9 flat config for VPO JavaScript files
export default [
    {
        ignores: [
            'node_modules/**',
            '.venv/**',
            'dist/**',
            'build/**',
            '**/*.pyc',
            '__pycache__/**',
            '.coverage',
            'htmlcov/**',
            '.pytest_cache/**',
            '.vscode/**',
            '.idea/**',
            '**/*.swp',
            '**/*.swo',
            '.DS_Store',
            'Thumbs.db'
        ]
    },
    {
        files: ['**/*.js'],
        languageOptions: {
            ecmaVersion: 'latest',
            sourceType: 'module',
            globals: {
                window: 'readonly',
                document: 'readonly',
                fetch: 'readonly',
                console: 'readonly'
            }
        },
        rules: {
            'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
            'camelcase': ['error', { properties: 'never' }],
            'no-console': ['warn', { allow: ['warn', 'error'] }],
            'semi': ['error', 'never'],
            'quotes': ['error', 'single', { avoidEscape: true }],
            'indent': ['error', 4],
            'space-before-function-paren': ['error', {
                anonymous: 'always',
                named: 'never',
                asyncArrow: 'always'
            }]
        }
    }
]
