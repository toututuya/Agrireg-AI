<template>
  <div id="agrireg-ai-app">
    <SiteHeader />
    <main id="main-content" ref="main" tabindex="-1">
      <router-view />
    </main>
  </div>
</template>

<script>
import SiteHeader from '@/components/SiteHeader.vue';
import '@/assets/interface.css';

export default {
  name: 'App',
  components: { SiteHeader },
  watch: {
    '$route.name'(name, previous) {
      if (previous && name !== previous) {
        this.$nextTick(() => this.$refs.main.focus({ preventScroll: true }));
      }
    }
  }
};
</script>
