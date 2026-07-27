import axios from "axios";
import { readBrowserStorage, removeBrowserStorage } from "@/lib/browser-storage";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = readBrowserStorage("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const detail = error.response?.data?.detail;
    const isDemoLifecycleFailure =
      detail === "demo_ended" || detail === "demo_credentials_replaced";

    if (error.response?.status === 401 && !isDemoLifecycleFailure) {
      removeBrowserStorage("token");
      removeBrowserStorage("refreshToken");
      removeBrowserStorage("user");
      removeBrowserStorage("activeTenantId");
      removeBrowserStorage("demoMetadata");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export default api;
