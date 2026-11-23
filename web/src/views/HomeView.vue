<template>
  <div class="workspace-frame frame">
    <router-view />
  </div>
</template>

<script>
export default { name: 'HomeView' };
</script>

<style scoped>
.workspace-frame { padding-block: 30px 56px; }
@media (max-width: 720px) {
  .workspace-frame { padding-block: 22px 36px; }
}
</style>
