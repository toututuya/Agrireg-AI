const { defineConfig } = require('@vue/cli-service');

module.exports = defineConfig({
  devServer: {
    port: Number(process.env.VUE_APP_DEV_PORT || 8082),
    historyApiFallback: true
  }
});
