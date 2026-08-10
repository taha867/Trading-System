import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { FormField, FormSelect, FormMultiSelect } from '@/components/custom';

function visibleFields(fields, mode) {
  return fields.filter((field) => !(mode !== 'edit' && field.hideOnCreate));
}

function buildDefaultValues(fields, row, mode) {
  return visibleFields(fields, mode).reduce((acc, field) => {
    if (field.component === 'multiselect') {
      acc[field.name] = row?.[field.name] ?? field.defaultValue ?? [];
    } else if (field.component === 'select') {
      acc[field.name] = row?.[field.name] != null ? String(row[field.name]) : (field.defaultValue ?? '');
    } else {
      acc[field.name] = row?.[field.name] ?? field.defaultValue ?? '';
    }
    return acc;
  }, {});
}

function inputTypeFor(component) {
  if (component === 'number') return 'number';
  if (component === 'date') return 'date';
  return 'text';
}

export function CrudDrawer({ config, open, mode, row, onOpenChange, entityLabel = 'record' }) {
  const schema = mode === 'edit' ? config.updateSchema : config.createSchema;

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm({
    // raw: true — handleSubmit receives the original typed values (e.g. the exact
    // rate string), never a Yup-cast float. See phase-0-frontend spec §8.1.
    resolver: yupResolver(schema, {}, { raw: true }),
    defaultValues: buildDefaultValues(config.fields, null, mode),
  });

  const createMutation = config.useCreate();
  const updateMutation = config.useUpdate();

  useEffect(() => {
    if (open) {
      reset(buildDefaultValues(config.fields, mode === 'edit' ? row : null, mode));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode, row]);

  const onSubmit = async (values) => {
    try {
      if (mode === 'edit') {
        await updateMutation.mutateAsync({ id: row.id, ...values });
      } else {
        await createMutation.mutateAsync(values);
      }
      onOpenChange(false);
    } catch {
      // fetchClient already toasted the backend's error detail — keep the
      // drawer open so the user can fix (e.g. a duplicate date) and retry.
    }
  };

  const isEdit = mode === 'edit';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{isEdit ? `Edit ${entityLabel}` : `Add ${entityLabel}`}</SheetTitle>
          <SheetDescription>
            {isEdit ? `Update this ${entityLabel}.` : `Fill in the details for the new ${entityLabel}.`}
          </SheetDescription>
        </SheetHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4 px-4">
          {visibleFields(config.fields, mode).map((field) => (
            <Controller
              key={field.name}
              name={field.name}
              control={control}
              disabled={isEdit && field.editableOnUpdate === false}
              render={({ field: rhfField }) => {
                if (field.component === 'select') {
                  return (
                    <FormSelect
                      {...rhfField}
                      label={field.label}
                      options={field.options}
                      placeholder={field.placeholder}
                      error={errors[field.name]?.message}
                    />
                  );
                }
                if (field.component === 'multiselect') {
                  return (
                    <FormMultiSelect
                      {...rhfField}
                      label={field.label}
                      options={field.options}
                      error={errors[field.name]?.message}
                    />
                  );
                }
                return (
                  <FormField
                    {...rhfField}
                    type={inputTypeFor(field.component)}
                    step={field.step}
                    label={field.label}
                    error={errors[field.name]?.message}
                  />
                );
              }}
            />
          ))}
          <SheetFooter className="flex-row justify-end gap-2 px-0">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving…' : 'Save'}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  );
}
