import Vue from 'vue';
import VueRouter from 'vue-router';

Vue.use(VueRouter);

const routes = [
  {
    path: '/',
    component: () => import('@/views/HomeView.vue'),
    children: [
      { path: '', redirect: 'graph' },
      {
        path: 'graph',
        name: 'graph',
        component: () => import('@/views/GraphView.vue')
      },
      {
        path: 'ask',
        name: 'ask',
        component: () => import('@/views/answer/AnswerView.vue')
      }
    ]
  },
  { path: '/answer', redirect: '/ask' },
  { path: '/japan', redirect: '/graph' },
  { path: '/japan_answer', redirect: '/ask' },
  { path: '/japan/dialog/:id', redirect: '/ask' },
  { path: '/dialog/:id', redirect: '/ask' },
  { path: '/login', redirect: '/graph' },
  { path: '/register', redirect: '/graph' },
  { path: '/forget', redirect: '/graph' },
  { path: '/reset', redirect: '/graph' }
];

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes,
  scrollBehavior() {
    return { x: 0, y: 0 };
  }
});

export default router;
