import { create } from "zustand";
import {
  listServices,
  listPlans,
  type Service,
  type Plan,
} from "@/features/admin/services/catalog-api";
import { listClients, type Client } from "@/features/admin/services/client-api";
import type { CatalogDataSourceContract, ClientCrudDataSourceContract } from "@/lib/data-source";

interface CatalogState {
  // Cache state
  services: Service[];
  plans: Record<string, Plan[]>; // serviceId -> plans
  clients: Client[];
  servicesLoaded: boolean;
  clientsLoaded: boolean;
  servicesInFlight: Promise<Service[]> | null;
  clientsInFlight: Promise<Client[]> | null;
  loadError: string | null;

  // Actions
  loadServices: (source?: CatalogDataSourceContract) => Promise<Service[]>;
  loadClients: (source?: ClientCrudDataSourceContract) => Promise<Client[]>;
  loadPlans: (serviceId: string, source?: CatalogDataSourceContract) => Promise<Plan[]>;
  invalidateServices: () => void;
  invalidatePlans: (serviceId?: string) => void;
  invalidateClients: () => void;
  clearAll: () => void;
}

export const useCatalogStore = create<CatalogState>((set, get) => ({
  // Initial state
  services: [],
  plans: {},
  clients: [],
  servicesLoaded: false,
  clientsLoaded: false,
  servicesInFlight: null,
  clientsInFlight: null,
  loadError: null,

  // Load services with deduplication
  loadServices: async (source?: CatalogDataSourceContract) => {
    const state = get();

    // Return cached if loaded
    if (state.servicesLoaded && state.services.length > 0) {
      return state.services;
    }

    // Deduplicate in-flight
    if (state.servicesInFlight) {
      return state.servicesInFlight;
    }

    const promise = (async () => {
      try {
        const data = await (source?.listServices ?? listServices)();
        set({
          services: data,
          servicesLoaded: true,
          loadError: null,
          servicesInFlight: null,
        });
        return data;
      } catch (error: any) {
        const msg = error?.response?.data?.detail || "Failed to load services";
        set({ loadError: msg, servicesInFlight: null });
        throw error;
      }
    })();

    set({ servicesInFlight: promise });
    return promise;
  },

  // Load plans for a service (cached per serviceId)
  loadPlans: async (serviceId: string, source?: CatalogDataSourceContract) => {
    const state = get();

    // Return cached if available
    if (state.plans[serviceId]) {
      return state.plans[serviceId];
    }

    try {
      const data = await (source?.listPlans ?? listPlans)(serviceId);
      set((prev) => ({
        plans: { ...prev.plans, [serviceId]: data },
      }));
      return data;
    } catch (error: any) {
      const msg = error?.response?.data?.detail || "Failed to load plans";
      set({ loadError: msg });
      throw error;
    }
  },

  // Load clients with deduplication
  loadClients: async (source?: ClientCrudDataSourceContract) => {
    const state = get();

    // Return cached if loaded
    if (state.clientsLoaded && state.clients.length > 0) {
      return state.clients;
    }

    // Deduplicate in-flight
    if (state.clientsInFlight) {
      return state.clientsInFlight;
    }

    const promise = (async () => {
      try {
        const data = await (source?.list ?? listClients)();
        set({
          clients: data,
          clientsLoaded: true,
          clientsInFlight: null,
        });
        return data;
      } catch (error: any) {
        const msg = error?.response?.data?.detail || "Failed to load clients";
        set({ loadError: msg, clientsInFlight: null });
        throw error;
      }
    })();

    set({ clientsInFlight: promise });
    return promise;
  },

  // Invalidate caches (after create/update/delete)
  invalidateServices: () => {
    set({ services: [], servicesLoaded: false, plans: {} });
  },

  invalidatePlans: (serviceId?: string) => {
    if (serviceId) {
      set((prev) => {
        const { [serviceId]: _, ...rest } = prev.plans;
        return { plans: rest };
      });
    } else {
      set({ plans: {} });
    }
  },

  invalidateClients: () => {
    set({ clients: [], clientsLoaded: false });
  },

  // Clear all (on logout)
  clearAll: () => {
    set({
      services: [],
      plans: {},
      clients: [],
      servicesLoaded: false,
      clientsLoaded: false,
      servicesInFlight: null,
      clientsInFlight: null,
      loadError: null,
    });
  },
}));
