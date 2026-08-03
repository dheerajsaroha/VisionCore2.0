import api from './apiClient';

const API_BASE = '/learning';

export const learningService = {
  // Categories
  getCategories: () => api.get(`${API_BASE}/categories`),
  createCategory: (data) => api.post(`${API_BASE}/categories`, data),

  // Courses & Modules
  getCourses: () => api.get(`${API_BASE}/courses`),
  createCourse: (data) => api.post(`${API_BASE}/courses`, data),
  addModule: (courseId, data) => api.post(`${API_BASE}/courses/${courseId}/modules`, data),

  // Enrollments & Progress
  enrollInCourse: (data) => api.post(`${API_BASE}/enrollments`, data),
  getEnrollments: (params) => api.get(`${API_BASE}/enrollments`, { params }),
  updateProgress: (enrollmentId, data) => api.post(`${API_BASE}/enrollments/${enrollmentId}/progress`, data),

  // Training Sessions
  getSessions: () => api.get(`${API_BASE}/sessions`),
  createSession: (data) => api.post(`${API_BASE}/sessions`, data),

  // Assessments & Quizzes
  getQuizzes: (params) => api.get(`${API_BASE}/quizzes`, { params }),
  createQuiz: (data) => api.post(`${API_BASE}/quizzes`, data),
  submitQuiz: (quizId, data, params) => api.post(`${API_BASE}/quizzes/${quizId}/submit`, data, { params }),

  // Skills
  getSkills: () => api.get(`${API_BASE}/skills`),
  createSkill: (data) => api.post(`${API_BASE}/skills`, data),
  addEmployeeSkill: (data) => api.post(`${API_BASE}/employee-skills`, data),
  getEmployeeSkills: (params) => api.get(`${API_BASE}/employee-skills`, { params }),

  // Certificates
  getCertificates: (params) => api.get(`${API_BASE}/certificates`, { params }),

  // Budget & Analytics
  getBudget: (params) => api.get(`${API_BASE}/budget`, { params }),
  getAnalytics: () => api.get(`${API_BASE}/analytics/dashboard`),
};
