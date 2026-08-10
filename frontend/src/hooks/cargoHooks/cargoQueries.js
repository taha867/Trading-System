import { useQuery } from '@tanstack/react-query';
import { cargoModeKeys, cargoCostBasisKeys, cargoShipmentKeys } from '@/utils/queryKeys';
import { listCargoModes, listCargoCostBases, listCargoShipments, getCargoShipment } from '@/services/cargoService';

export function useCargoModes(params) {
  return useQuery({
    queryKey: cargoModeKeys.list(params),
    queryFn: () => listCargoModes(params),
  });
}

export function useCargoCostBases(params) {
  return useQuery({
    queryKey: cargoCostBasisKeys.list(params),
    queryFn: () => listCargoCostBases(params),
  });
}

export function useCargoShipments(params) {
  return useQuery({
    queryKey: cargoShipmentKeys.list(params),
    queryFn: () => listCargoShipments(params),
  });
}

export function useCargoShipment(id) {
  return useQuery({
    queryKey: cargoShipmentKeys.detail(id),
    queryFn: () => getCargoShipment(id),
    enabled: Boolean(id),
  });
}
