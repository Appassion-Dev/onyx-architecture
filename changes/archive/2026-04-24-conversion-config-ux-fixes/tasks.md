## 1. Back Navigation

- [x] 1.1 Import `useNavigate` and `ArrowLeft` (from `lucide-react`) into `ConversionConfigPage`
- [x] 1.2 Add a back button above the `<h1>` that calls `navigate('/conversions')` on click

## 2. Fix Empty Fields on SPA Navigation

- [x] 2.1 Change the `queryKey` in `ConversionConfigPage`'s `useQuery` from `['gads-conversion-config']` to `['gads-conversion-config-full']`
- [x] 2.2 Update the `invalidateQueries` call in the mutation's `onSuccess` to use `['gads-conversion-config-full']`

## 3. Per-Row Save Loading State

- [x] 3.1 Add `savingType` state: `const [savingType, setSavingType] = useState<string | null>(null)`
- [x] 3.2 In `handleSave`, call `setSavingType(type)` before `mutation.mutate(...)`
- [x] 3.3 Add `onSettled` to the mutation options that calls `setSavingType(null)`
- [x] 3.4 Replace `mutation.isPending` in the Save button's `disabled` prop with `savingType === cfg.conversion_type`
- [x] 3.5 Replace `mutation.isPending` in the Save button's spinner condition with `savingType === cfg.conversion_type`
