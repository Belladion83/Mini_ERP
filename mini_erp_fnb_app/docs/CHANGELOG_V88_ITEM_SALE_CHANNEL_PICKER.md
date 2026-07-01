# V88 - Item Master Sales Channel Picker

## Scope
Update Item Master > Sales tab > Opened Sale Channels control.

## Changes
- Replace the old native multi-select/listbox behavior with a compact ERP-style sale channel picker.
- Show currently opened sale channels as chips directly on the Sales tab.
- Add searchable list for sale channel code/name/type.
- Support multiple channel selection with checkbox rows.
- Add Select shown / Clear / Done actions.
- Keep the underlying field as `sale_channel_ids`, so the existing backend save logic remains compatible.
- Exclude this multiple-select field from the generic single-value searchable select initializer.

## No SQL migration required
This version only changes UI/JS/CSS behavior.
