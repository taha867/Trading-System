// Model names no longer repeat the brand ("Y15", "A35"), so every picker shows brand + model: "Vivo Y15".
export function modelLabel(model, brandNameById) {
  return `${brandNameById[model.brand_id] ?? ''} ${model.name}`.trim();
}
