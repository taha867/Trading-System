import { useMutation, useQueryClient } from '@tanstack/react-query';
import { cargoModeKeys, cargoCostBasisKeys, cargoShipmentKeys, purchaseOrderKeys } from '@/utils/queryKeys';
import * as cargoService from '@/services/cargoService';

export function useCreateCargoMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.createCargoMode,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoModeKeys.lists() }),
  });
}

export function useUpdateCargoMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.updateCargoMode,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoModeKeys.lists() }),
  });
}

export function useDeleteCargoMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.deleteCargoMode,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoModeKeys.lists() }),
  });
}

export function useCreateCargoCostBasis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.createCargoCostBasis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoCostBasisKeys.lists() }),
  });
}

export function useUpdateCargoCostBasis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.updateCargoCostBasis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoCostBasisKeys.lists() }),
  });
}

export function useDeleteCargoCostBasis() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.deleteCargoCostBasis,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: cargoCostBasisKeys.lists() }),
  });
}

export function useCreateCargoShipment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cargoService.createCargoShipment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: cargoShipmentKeys.lists() });
      // A shipment mutates every attached PO's status AND every one of its lines'
      // landed_cost_pkr in the same backend transaction. Invalidating just
      // purchaseOrderKeys.lists() would leave a PurchaseOrderDetail page open in
      // another tab showing stale (null) landed costs — invalidate the whole
      // purchaseOrders key space (lists + every cached detail) instead, the same
      // cross-screen invalidation CLAUDE.md §3.4 describes for PurchaseOrderForm.
      queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.all });
    },
  });
}
