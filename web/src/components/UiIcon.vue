<template>
  <svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path :d="paths[name]" />
  </svg>
</template>

<script>
const paths = {
  search: 'M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0ZM16 16l5 5',
  graph: 'M8 12a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0Zm13-6a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0Zm0 12a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0ZM8 11l8-4m-8 6 8 4',
  chat: 'M21 5H3v13h4v3l4-3h10V5ZM7 9h10m-10 4h6',
  task: 'M5 4h14v5H5zM5 15h14v5H5zM8 9v6m8-6v6',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  external: 'M13 5h6v6m0-6-9 9m7 0v5H5V7h5',
  plus: 'M12 5v14M5 12h14',
  chevron: 'm6 9 6 6 6-6',
  document: 'M6 3h8l4 4v14H6zM14 3v5h4M9 12h6m-6 4h6',
  send: 'm5 12 15-8-5 16-3-6-7-2Zm7 2 8-10',
  check: 'm5 12 4 4L19 6',
  alert: 'M12 3 2.8 19h18.4L12 3ZM12 9v4m0 3h.01'
};

export default {
  name: 'UiIcon',
  props: { name: { type: String, required: true } },
  data: () => ({ paths })
};
</script>
