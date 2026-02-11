module.exports = {
  apps: [{
    name: 'michael',
    script: './dist/start.js',
    cwd: '/Users/ldm/work/workspace/ai_agentic/opencode-demo/michael',
    node_args: '--experimental-vm-modules',
    env: {
      NODE_ENV: 'production',
    },
    // Restart on failure
    max_restarts: 10,
    restart_delay: 5000,
    // Logs
    error_file: './data/logs/pm2-error.log',
    out_file: './data/logs/pm2-out.log',
    merge_logs: true,
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
  }],
};
