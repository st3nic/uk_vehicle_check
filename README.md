# UK Vehicle Check

Home Assistant integration that tracks a vehicle's tax and MOT dates from DVLA, with reminders before they run out.

DVLA isn't issuing new keys for its Vehicle Enquiry API at the moment, so this integration reads the public [Check if a vehicle is taxed and has an MOT](https://vehicleenquiry.service.gov.uk/) service instead, the same way you would in a browser. It checks each vehicle **once a day** at most.


## Install

1. In HACS, add `https://github.com/st3nic/uk_vehicle_check` as a custom repository (type: Integration).

2. Search for UK Vehicle Check and download it, then restart Home Assistant.

3. Go to Settings > Devices & services > Add Integration and search for UK Vehicle Check.

4. Enter the registration number.

To add another vehicle, add the integration again with the other registration.


## What you get

Each vehicle gets its own device:

| Entity | Example |
|---|---|
| Tax status | `Taxed`, `Untaxed`, `SORN` |
| Tax due | `2027-07-01` |
| Tax days left | `258` |
| MOT status | `Valid`, `Expired`, `No details held` |
| MOT expires | `2027-07-02` |
| MOT days left | `259` |
| Tax or MOT due soon | On when either is due within 28 days, or has run out |
| Calendar | Tax due and MOT expiry as all-day events |
| Last checked | When DVLA was last checked |

The make, colour, fuel type, engine size and CO₂ figures are attributes of the Tax status sensor.

To change the 28 days, go to Settings > Devices & services > UK Vehicle Check, choose the vehicle and click Configure.

New vehicles don't need an MOT until they're 3 years old, so their MOT dates stay empty until then.


## Reminder blueprint

Sends a notification to your phone a set number of days before tax or MOT is due, titled with the registration, e.g. **AB12 CDE – MOT**: "MOT is due in 28 days (2 July 2027)". Tapping the notification opens the vehicle's page in Home Assistant. By default it reminds you 28, 14, 7 and 1 days before, at 9am.

Go to Settings > Automations & scenes > Blueprints > Import blueprint and paste:
`https://github.com/st3nic/uk_vehicle_check/blob/master/blueprints/automation/uk_vehicle_check_reminder.yaml`

Then create an automation from it for each vehicle, choosing its Tax days left and MOT days left sensors and your phone.

To check it works, open the automation and choose Run from the ⋮ menu. That sends a test notification with both the tax and MOT dates.

If you imported the blueprint before an update, go to Settings > Automations & scenes > Blueprints, click ⋮ next to it and choose Re-import blueprint.

Tip: you can MOT a vehicle up to a month (minus a day) before it runs out and keep the same renewal date, so a 28-day reminder gives you time to book.


## If something goes wrong

- If a check fails, the last dates found are kept, so your reminders keep working. It tries again later.
- If DVLA changes its website so the results can't be read, a repair notice appears under Settings > System > Repairs. Please [open an issue](https://github.com/st3nic/uk_vehicle_check/issues) if that happens.
- After you renew tax or get an MOT, DVLA can take a couple of days to update.
