/*
 * etl-wmdplotter — a CloudTAK ETL task that pushes WMD PLOTTER hazard zones to
 * TAK users.
 *
 * Built against @tak-ps/etl (dfpc-coe/etl-base) v10.x. Two invocation modes:
 *
 *   Webhook (event-driven, primary): WMD PLOTTER POSTs a hazard FeatureCollection
 *     to this layer's webhook URL the instant a responder broadcasts an incident.
 *     controlWebhooks() (via `static webhooks`) receives it, transforms, submits.
 *
 *   Schedule (optional): control() polls a WMD PLOTTER instance for active
 *     incidents and submits them, keeping a live layer in sync.
 *
 * The transform is the tested pure function in ./transform.js (transform.test.js).
 * This file is the CloudTAK wiring; it can only be exercised against a real
 * CloudTAK deployment (AWS/ECR), so it is intentionally thin.
 *
 * Deploy: see README.md — `npx cloudtak-etl` builds and pushes; register in the
 * CloudTAK Admin UI and attach to a Connection's Layer.
 */

import ETL, {
    Event, SchemaType, handler as internal, local,
    InvocationType, DataFlowType,
} from '@tak-ps/etl';
import { Type, TSchema, Static } from '@sinclair/typebox';
import type Schema from '@openaddresses/batch-schema';
// The build (tsc/esbuild) compiles this alongside; the same module is unit-tested
// as CommonJS in transform.test.js.
import { wmdToCot } from './transform.js';

/**
 * Operator-facing configuration for this layer, surfaced in the CloudTAK UI and
 * read back via this.env(). Only needed for the Schedule (pull) mode; a pure
 * webhook layer can leave the URL blank.
 */
const InputSchema = Type.Object({
    WMD_API_URL: Type.String({
        default: '',
        description: 'Base URL of the WMD PLOTTER instance to poll for active incidents (Schedule mode only). Leave blank for webhook-only layers.',
    }),
    WMD_API_TOKEN: Type.String({
        default: '',
        description: 'Bearer token for the WMD PLOTTER instance (Schedule mode only). Stored as a secret.',
    }),
    STALE_MINUTES: Type.Integer({
        default: 60,
        description: 'How long (minutes) a broadcast hazard zone remains live in ATAK before going stale.',
    }),
    DEBUG: Type.Boolean({
        default: false,
        description: 'Log the transformed FeatureCollection before submitting.',
    }),
});

export default class Task extends ETL {
    static name = 'etl-wmdplotter';
    static flow = [DataFlowType.Incoming];                         // we bring data INTO TAK
    static invocation = [InvocationType.Webhook, InvocationType.Schedule];

    async schema(type: SchemaType = SchemaType.Input): Promise<TSchema> {
        if (type === SchemaType.Input) return InputSchema;
        // Output: the properties each submitted feature carries. Advertising them
        // lets operators filter/style in CloudTAK.
        return Type.Object({
            callsign: Type.String(),
            remarks: Type.String(),
            threshold_ppm: Type.Optional(Type.Number()),
            level: Type.Optional(Type.String()),
        });
    }

    /**
     * Webhook (event-driven) entry point. WMD PLOTTER POSTs:
     *   { meta: { name, kind, agent, rate_kg_min, wind_label, stability, ... },
     *     geojson: <WMD model FeatureCollection> }
     * We transform and submit. This is the path that "pushes to users" the
     * moment a plume is computed.
     */
    static webhooks = async (schema: Schema, task: Task): Promise<void> => {
        await schema.post('/broadcast', {
            name: 'Broadcast Hazard',
            group: 'WMD PLOTTER',
            description: 'Receive a WMD PLOTTER hazard FeatureCollection and push it to the TAK layer.',
            body: Type.Object({
                meta: Type.Object({
                    name: Type.Optional(Type.String()),
                    kind: Type.Optional(Type.String()),
                    agent: Type.Optional(Type.String()),
                    rate_kg_min: Type.Optional(Type.Number()),
                    wind_label: Type.Optional(Type.String()),
                    stability: Type.Optional(Type.String()),
                    time: Type.Optional(Type.String()),
                    source_uid: Type.Optional(Type.String()),
                }),
                geojson: Type.Any(),
            }),
            res: Type.Object({ status: Type.String(), submitted: Type.Integer() }),
        }, async (req, res) => {
            const env = await task.env(InputSchema);
            const meta = Object.assign(
                { stale_minutes: env.STALE_MINUTES },
                req.body.meta || {},
            );
            const fc = wmdToCot(req.body.geojson, meta);
            if (env.DEBUG) console.log(JSON.stringify(fc, null, 2));
            await task.submit(fc);
            res.json({ status: 'ok', submitted: fc.features.length });
        });
    };

    /**
     * Schedule (pull) entry point. Fetches active incidents from the configured
     * WMD PLOTTER instance and submits them. Optional — disabled by default in
     * capabilities.json.
     */
    async control(): Promise<void> {
        const env = await this.env(InputSchema);
        if (!env.WMD_API_URL) {
            // Webhook-only layer: nothing to pull. Submit an empty set so the
            // layer state is well-defined rather than erroring.
            await this.submit({ type: 'FeatureCollection', features: [] });
            return;
        }

        const url = new URL('/api/incidents/active.geojson', env.WMD_API_URL);
        const incidents = await this.fetch(url, {
            headers: env.WMD_API_TOKEN ? { Authorization: `Bearer ${env.WMD_API_TOKEN}` } : {},
        }) as { incidents?: Array<{ meta: object; geojson: object }> };

        const features: object[] = [];
        for (const inc of (incidents.incidents || [])) {
            const meta = Object.assign({ stale_minutes: env.STALE_MINUTES }, inc.meta || {});
            const fc = wmdToCot(inc.geojson, meta);
            features.push(...fc.features);
        }
        await this.submit({ type: 'FeatureCollection', features });
    }
}

// Standard @tak-ps/etl entrypoint: `local` for dev, Lambda `handler` in cloud.
await local(new Task(import.meta.url), import.meta.url);
export async function handler(event: Event = {}) {
    return await internal(new Task(import.meta.url), event);
}
