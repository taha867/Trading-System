export const authKeys = {
  all: ['auth'],
  me: () => [...authKeys.all, 'me'],
};

export const exchangeRateKeys = {
  all: ['exchangeRates'],
  lists: () => [...exchangeRateKeys.all, 'list'],
  list: (params) => [...exchangeRateKeys.lists(), params],
};

export const paymentMethodKeys = {
  all: ['paymentMethods'],
  lists: () => [...paymentMethodKeys.all, 'list'],
  list: (params) => [...paymentMethodKeys.lists(), params],
};

export const categoryKeys = {
  all: ['categories'],
  lists: () => [...categoryKeys.all, 'list'],
  list: (params) => [...categoryKeys.lists(), params],
};

export const modelKeys = {
  all: ['models'],
  lists: () => [...modelKeys.all, 'list'],
  list: (params) => [...modelKeys.lists(), params],
};

export const itemKeys = {
  all: ['items'],
  lists: () => [...itemKeys.all, 'list'],
  list: (params) => [...itemKeys.lists(), params],
};

export const partyKeys = {
  all: ['parties'],
  lists: () => [...partyKeys.all, 'list'],
  list: (params) => [...partyKeys.lists(), params],
  statement: (id) => [...partyKeys.all, 'statement', id],
};

export const purchaseOrderKeys = {
  all: ['purchaseOrders'],
  lists: () => [...purchaseOrderKeys.all, 'list'],
  list: (params) => [...purchaseOrderKeys.lists(), params],
  detail: (id) => [...purchaseOrderKeys.all, 'detail', id],
};

export const cargoModeKeys = {
  all: ['cargoModes'],
  lists: () => [...cargoModeKeys.all, 'list'],
  list: (params) => [...cargoModeKeys.lists(), params],
};

export const cargoCostBasisKeys = {
  all: ['cargoCostBases'],
  lists: () => [...cargoCostBasisKeys.all, 'list'],
  list: (params) => [...cargoCostBasisKeys.lists(), params],
};

export const cargoShipmentKeys = {
  all: ['cargoShipments'],
  lists: () => [...cargoShipmentKeys.all, 'list'],
  list: (params) => [...cargoShipmentKeys.lists(), params],
  detail: (id) => [...cargoShipmentKeys.all, 'detail', id],
};

export const stockLotKeys = {
  all: ['stockLots'],
  lists: () => [...stockLotKeys.all, 'list'],
  list: (params) => [...stockLotKeys.lists(), params],
  detail: (id) => [...stockLotKeys.all, 'detail', id],
};

export const stockMovementKeys = {
  all: ['stockMovements'],
  lists: () => [...stockMovementKeys.all, 'list'],
  list: (params) => [...stockMovementKeys.lists(), params],
};

export const salesOrderKeys = {
  all: ['salesOrders'],
  lists: () => [...salesOrderKeys.all, 'list'],
  list: (params) => [...salesOrderKeys.lists(), params],
  detail: (id) => [...salesOrderKeys.all, 'detail', id],
};

export const paymentAccountKeys = {
  all: ['paymentAccounts'],
  lists: () => [...paymentAccountKeys.all, 'list'],
  list: (params) => [...paymentAccountKeys.lists(), params],
  balances: () => [...paymentAccountKeys.all, 'balances'],
};

export const paymentTransactionKeys = {
  all: ['paymentTransactions'],
  lists: () => [...paymentTransactionKeys.all, 'list'],
  list: (params) => [...paymentTransactionKeys.lists(), params],
};

export const expenseCategoryKeys = {
  all: ['expenseCategories'],
  lists: () => [...expenseCategoryKeys.all, 'list'],
  list: (params) => [...expenseCategoryKeys.lists(), params],
};

export const recurringExpenseTemplateKeys = {
  all: ['recurringExpenseTemplates'],
  lists: () => [...recurringExpenseTemplateKeys.all, 'list'],
  list: (params) => [...recurringExpenseTemplateKeys.lists(), params],
};

export const expenseKeys = {
  all: ['expenses'],
  lists: () => [...expenseKeys.all, 'list'],
  list: (params) => [...expenseKeys.lists(), params],
};

// Every reporting endpoint is a single bounded object/array, never a paginated
// list — no domain here ever needs .lists()/.list(params)/.detail(id). Shaped
// after paymentAccountKeys.balances(), the existing precedent for a bare,
// params-varying, non-list key.
export const reportingKeys = {
  all: ['reporting'],
  balanceStatement: () => [...reportingKeys.all, 'balance-statement'],
  sellThrough: (windowDays) => [...reportingKeys.all, 'sell-through', windowDays],
  reorderPriority: (windowDays) => [...reportingKeys.all, 'reorder-priority', windowDays],
  margin: (windowDays) => [...reportingKeys.all, 'margin', windowDays],
};
