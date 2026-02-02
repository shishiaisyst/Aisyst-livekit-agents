/**
 * ElevenLabs Post-Call Webhook Handler
 *
 * This Edge Function receives webhooks from ElevenLabs after voice calls,
 * verifies the signature, extracts order/call data, stores in Supabase,
 * creates Stripe payment links, and sends SMS confirmations.
 * 
 * MODIFIED: Updated to use conversation_id instead of call_id for idempotency key
 * as ElevenLabs webhook payload uses conversation_id as the unique identifier.
 */

import 'jsr:@supabase/functions-js/edge-runtime.d.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { createLogger, type Logger } from '../_shared/logger.ts';

// CORS headers for preflight requests
const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers':
        'authorization, x-client-info, apikey, content-type, elevenlabs-signature',
    'Access-Control-Allow-Methods': 'POST, OPTIONS'
};

// ============================================================================
// TYPES
// ============================================================================

// MODIFIED: Updated interface to match actual ElevenLabs webhook payload structure
// The payload is wrapped in { type, event_timestamp, data: { ... } }
interface ElevenLabsWebhookPayload {
    type: string;  // MODIFIED: Added - e.g., "post_call_transcription"
    event_timestamp: number;  // MODIFIED: Added
    data: {  // MODIFIED: Added nested data object
        agent_id: string;
        conversation_id: string;  // MODIFIED: This is the unique identifier which we can use for idempotency key (not call_id)
        status: string;
        user_id: string;  // This is the caller's phone number
        branch_id: string | null;
        version_id: string | null;
        transcript: TranscriptEntry[];  // MODIFIED: Changed from string to array
        metadata: ElevenLabsMetadata;
        analysis: ElevenLabsAnalysis;
        conversation_initiation_client_data?: Record<string, unknown>;
    };
}

// MODIFIED: Added new interface for transcript entries
interface TranscriptEntry {
    role: 'agent' | 'user';
    message: string;
    time_in_call_secs: number;
    tool_calls: unknown[];
    tool_results: unknown[];
    // LLM Performance Metrics fields (added for Cerebras comparison)
    conversation_turn_metrics?: {
        metrics?: {
            convai_llm_service_ttfb?: { elapsed_time: number };
            convai_llm_service_ttf_sentence?: { elapsed_time: number };
            convai_llm_service_tt_last_sentence?: { elapsed_time: number };
            convai_tts_service_ttfb?: { elapsed_time: number };
            convai_asr_trailing_service_latency?: { elapsed_time: number };
        };
    };
    llm_usage?: {
        model_usage?: Record<string, {
            input?: { tokens: number; price: number };
            input_cache_read?: { tokens: number; price: number };
            input_cache_write?: { tokens: number; price: number };
            output_total?: { tokens: number; price: number };
        }>;
    };
    rag_retrieval_info?: {
        rag_latency_secs?: number;
        embedding_model?: string;
    };
}

// MODIFIED: Added new interface for metadata
interface ElevenLabsMetadata {
    start_time_unix_secs: number;
    call_duration_secs: number;
    cost: number;
    phone_call?: {
        direction: string;
        phone_number_id: string;
        agent_number: string;
        external_number: string;  // This is the caller's phone number
        type: string;
        call_sid: string;  // Twilio call SID
    };
    termination_reason: string;
    error: string | null;
}

// MODIFIED: Added new interface for analysis
interface ElevenLabsAnalysis {
    evaluation_criteria_results: Record<string, unknown>;
    data_collection_results: Record<string, {
        data_collection_id: string;
        value: unknown;
        json_schema: Record<string, unknown>;
        rationale: string;
    }>;
    call_successful: string;
    transcript_summary: string;
    call_summary_title: string;
}

interface ExtractedOrder {
    customer_name: string;
    customer_phone: string;
    customer_email?: string;
    items: OrderItem[];
    total_order_value: number;
    order_type: string;
    special_instructions?: string;
    promo_code?: string;
    payment_status: string;
}

interface OrderItem {
    name: string;
    quantity: number;
    price: number;
}

interface VoiceCallRecord {
    conversation_id: string;  // MODIFIED: Changed from call_id to conversation_id
    agent_id: string;
    caller_number: string;
    duration_seconds: number;
    status: string;
    transcript: string;
    sentiment?: string;
    summary?: string;
}

// Latency Metrics interface (for latency_metrics table)
interface LatencyMetrics {
    call_id: string;
    turn_number: number;
    sequence_id: number;
    stt_provider: string;
    stt_model: string | null;
    llm_provider: string;
    llm_model: string;
    tts_provider: string;
    tts_model: string | null;
    ttfb_ms: number | null;
    end_to_end_ms: number | null;
    vad_duration_ms: number | null;
    stt_duration_ms: number | null;
    llm_ttfb_ms: number | null;
    tts_total_ms: number | null;
    user_speech_duration_ms: number | null;
    agent_speech_duration_ms: number | null;
    llm_tokens_in: number;
    llm_tokens_out: number;
    transcript_length: number;
    response_length: number;
    region: string;
    agent_version: string;
    had_error: boolean;
    error_component: string | null;
    error_message: string | null;
    metric_timestamp: string;
}

// ============================================================================
// WEBHOOK SIGNATURE VERIFICATION
// ============================================================================

async function verifyWebhookSignature(
    signature: string | null,
    body: string,
    secret: string
): Promise<{ verified: boolean; error?: string }> {
    if (!signature) {
        return { verified: false, error: 'Missing elevenlabs-signature header' };
    }

    try {
        // Parse signature header (format: t=timestamp,v0=signature)
        const parts = signature.split(',');
        const timestampPart = parts.find((p) => p.startsWith('t='));
        const signaturePart = parts.find((p) => p.startsWith('v0='));

        if (!timestampPart || !signaturePart) {
            return { verified: false, error: 'Invalid signature format' };
        }

        const timestamp = timestampPart.slice(2);
        const expectedSignature = signaturePart.slice(3);

        // Check timestamp (reject if older than 5 minutes)
        const timestampMs = parseInt(timestamp) * 1000;
        const now = Date.now();
        const fiveMinutes = 5 * 60 * 1000;

        if (now - timestampMs > fiveMinutes) {
            return {
                verified: false,
                error: 'Webhook timestamp too old (replay attack prevention)'
            };
        }

        // Compute expected signature
        const signedPayload = `${timestamp}.${body}`;
        const encoder = new TextEncoder();
        const key = await crypto.subtle.importKey(
            'raw',
            encoder.encode(secret),
            { name: 'HMAC', hash: 'SHA-256' },
            false,
            ['sign']
        );

        const signatureBytes = await crypto.subtle.sign('HMAC', key, encoder.encode(signedPayload));

        const computedSignature = Array.from(new Uint8Array(signatureBytes))
            .map((b) => b.toString(16).padStart(2, '0'))
            .join('');

        if (computedSignature !== expectedSignature) {
            return { verified: false, error: 'Signature mismatch' };
        }

        return { verified: true };
    } catch (error) {
        return { verified: false, error: `Verification error: ${error}` };
    }
}

// ============================================================================
// DATA EXTRACTION
// ============================================================================

// MODIFIED: Updated function to work with new payload structure
function extractOrderFromTranscript(payload: ElevenLabsWebhookPayload): ExtractedOrder | null {
    try {
        // MODIFIED: Access data from nested payload.data structure
        const analysis = payload.data.analysis;
        const metadata = payload.data.metadata;
        const dataCollection = analysis?.data_collection_results;

        // MODIFIED: Extract customer name from data_collection_results if available
        const customerName = dataCollection?.name?.value as string || 'Phone Customer';
        
        // MODIFIED: Get caller phone from metadata.phone_call.external_number
        const callerPhone = metadata?.phone_call?.external_number || payload.data.user_id || '';

        // If ElevenLabs provides structured data_collection_results, use it
        if (dataCollection) {
            return {
                customer_name: customerName,
                customer_phone: callerPhone,
                customer_email: dataCollection.email?.value as string,
                items: (dataCollection.items?.value as OrderItem[]) || [],
                total_order_value: (dataCollection.total?.value as number) || 0,
                order_type: (dataCollection.order_type?.value as string) || 'phone',
                special_instructions: dataCollection.special_instructions?.value as string,
                promo_code: dataCollection.promo_code?.value as string,
                payment_status: (dataCollection.payment_status?.value as string) || 'pending'
            };
        }

        // Fallback: Return basic order with customer info
        return {
            customer_name: customerName,
            customer_phone: callerPhone,
            items: [],
            total_order_value: 0,
            order_type: 'phone',
            payment_status: 'pending'
        };
    } catch {
        return null;
    }
}

// MODIFIED: Updated function to work with new payload structure using conversation_id
function extractVoiceCallRecord(payload: ElevenLabsWebhookPayload): VoiceCallRecord {
    // MODIFIED: Combine all transcript messages into a single string
    const transcriptText = payload.data.transcript
        .map(entry => `${entry.role}: ${entry.message}`)
        .join('\n');

    return {
        // MODIFIED: Use conversation_id instead of call_id
        conversation_id: payload.data.conversation_id,
        agent_id: payload.data.agent_id,
        // MODIFIED: Get caller number from metadata.phone_call.external_number
        caller_number: payload.data.metadata?.phone_call?.external_number || payload.data.user_id || '',
        // MODIFIED: Get duration from metadata.call_duration_secs
        duration_seconds: payload.data.metadata?.call_duration_secs || 0,
        status: payload.data.status,
        transcript: transcriptText,
        // MODIFIED: Get summary from analysis.transcript_summary
        sentiment: payload.data.analysis?.call_successful,
        summary: payload.data.analysis?.transcript_summary
    };
}

// ============================================================================
// LATENCY METRICS EXTRACTION (for latency_metrics table)
// ============================================================================

/**
 * Extracts latency metrics from the webhook payload for the latency_metrics table.
 * This aggregates all turn-level metrics into a single record per call.
 */
function extractLatencyMetrics(payload: ElevenLabsWebhookPayload): LatencyMetrics | null {
    try {
        const data = payload.data;
        const transcript = data.transcript || [];
        const metadata = data.metadata;
        
        // Count turns
        const agentTurns = transcript.filter(turn => turn.role === 'agent');
        const totalTurns = transcript.length;
        
        if (totalTurns === 0) {
            return null;
        }
        
        // Aggregate metrics
        let totalLlmTtfb = 0;
        let llmTtfbCount = 0;
        let totalTtsTtfb = 0;
        let ttsTtfbCount = 0;
        let totalSttLatency = 0;
        let sttLatencyCount = 0;
        let totalInputTokens = 0;
        let totalOutputTokens = 0;
        let totalTranscriptLength = 0;
        let totalResponseLength = 0;
        
        // Calculate user and agent speech duration from time_in_call_secs
        let userSpeechDuration = 0;
        let agentSpeechDuration = 0;
        let previousTime = 0;
        
        for (let i = 0; i < transcript.length; i++) {
            const turn = transcript[i];
            const currentTime = turn.time_in_call_secs || 0;
            const turnDuration = currentTime - previousTime;
            
            if (turn.role === 'user') {
                userSpeechDuration += turnDuration > 0 ? turnDuration : 0;
                totalTranscriptLength += turn.message?.length || 0;
                
                // STT latency from ASR trailing service
                const asrLatency = turn.conversation_turn_metrics?.metrics?.convai_asr_trailing_service_latency?.elapsed_time;
                if (asrLatency !== undefined) {
                    totalSttLatency += asrLatency * 1000; // Convert to ms
                    sttLatencyCount++;
                }
            } else if (turn.role === 'agent') {
                agentSpeechDuration += turnDuration > 0 ? turnDuration : 0;
                totalResponseLength += turn.message?.length || 0;
                
                const metrics = turn.conversation_turn_metrics?.metrics;
                const llmUsage = turn.llm_usage?.model_usage;
                
                // LLM TTFB
                if (metrics?.convai_llm_service_ttfb?.elapsed_time !== undefined) {
                    totalLlmTtfb += metrics.convai_llm_service_ttfb.elapsed_time * 1000;
                    llmTtfbCount++;
                }
                
                // TTS TTFB
                if (metrics?.convai_tts_service_ttfb?.elapsed_time !== undefined) {
                    totalTtsTtfb += metrics.convai_tts_service_ttfb.elapsed_time * 1000;
                    ttsTtfbCount++;
                }
                
                // Token usage
                if (llmUsage) {
                    for (const usage of Object.values(llmUsage)) {
                        totalInputTokens += (usage.input?.tokens || 0) + (usage.input_cache_read?.tokens || 0);
                        totalOutputTokens += usage.output_total?.tokens || 0;
                    }
                }
            }
            
            previousTime = currentTime;
        }
        
        // Calculate averages
        const avgLlmTtfb = llmTtfbCount > 0 ? totalLlmTtfb / llmTtfbCount : null;
        const avgTtsTtfb = ttsTtfbCount > 0 ? totalTtsTtfb / ttsTtfbCount : null;
        const avgSttLatency = sttLatencyCount > 0 ? totalSttLatency / sttLatencyCount : null;
        
        // Calculate end-to-end latency (LLM TTFB + TTS TTFB)
        const endToEndMs = avgLlmTtfb !== null && avgTtsTtfb !== null 
            ? avgLlmTtfb + avgTtsTtfb 
            : avgLlmTtfb;
        
        // Calculate TTFB (first agent response time)
        const firstAgentTurn = agentTurns[0];
        const ttfbMs = firstAgentTurn?.conversation_turn_metrics?.metrics?.convai_llm_service_ttfb?.elapsed_time !== undefined
            ? firstAgentTurn.conversation_turn_metrics.metrics.convai_llm_service_ttfb.elapsed_time * 1000
            : null;
        
        // Check for errors
        const hasError = metadata?.error !== null && metadata?.error !== undefined;
        const errorMessage = metadata?.error || null;
        const errorComponent = hasError ? 'call' : null;
        
        return {
            call_id: data.conversation_id,
            turn_number: totalTurns,
            sequence_id: 1, // Single record per call
            stt_provider: 'Eleven Labs',
            stt_model: 'Scribe v2 Realtime',
            llm_provider: 'Cerebras',
            llm_model: 'gpt-oss-120b',
            tts_provider: 'Eleven Labs',
            tts_model: 'Flash v2.5',
            ttfb_ms: ttfbMs !== null ? Number(ttfbMs.toFixed(2)) : null,
            end_to_end_ms: endToEndMs !== null ? Number(endToEndMs.toFixed(2)) : null,
            vad_duration_ms: null, // Not available in payload
            stt_duration_ms: avgSttLatency !== null ? Number(avgSttLatency.toFixed(2)) : null,
            llm_ttfb_ms: avgLlmTtfb !== null ? Number(avgLlmTtfb.toFixed(2)) : null,
            tts_total_ms: avgTtsTtfb !== null ? Number(avgTtsTtfb.toFixed(2)) : null,
            user_speech_duration_ms: userSpeechDuration > 0 ? userSpeechDuration * 1000 : null,
            agent_speech_duration_ms: agentSpeechDuration > 0 ? agentSpeechDuration * 1000 : null,
            llm_tokens_in: totalInputTokens,
            llm_tokens_out: totalOutputTokens,
            transcript_length: totalTranscriptLength,
            response_length: totalResponseLength,
            region: 'Australia',
            agent_version: '1.0.0',
            had_error: hasError,
            error_component: errorComponent,
            error_message: errorMessage,
            metric_timestamp: new Date().toISOString()
        };
    } catch (error) {
        console.error('Error extracting latency metrics:', error);
        return null;
    }
}

// ============================================================================
// STRIPE INTEGRATION
// ============================================================================

async function createStripePaymentLink(
    order: ExtractedOrder,
    stripeSecretKey: string
): Promise<string | null> {
    if (!stripeSecretKey || order.items.length === 0) {
        return null;
    }

    try {
        // Create line items for Stripe
        const lineItems = order.items.map((item) => ({
            price_data: {
                currency: 'usd',
                product_data: {
                    name: item.name
                },
                unit_amount: Math.round(item.price * 100) // Stripe uses cents
            },
            quantity: item.quantity
        }));

        // Create payment link via Stripe API
        const response = await fetch('https://api.stripe.com/v1/payment_links', {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${stripeSecretKey}`,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: new URLSearchParams({
                'line_items[0][price_data][currency]': 'usd',
                'line_items[0][price_data][product_data][name]': `Order for ${order.customer_name}`,
                'line_items[0][price_data][unit_amount]': Math.round(
                    order.total_order_value * 100
                ).toString(),
                'line_items[0][quantity]': '1'
            })
        });

        const data = await response.json();
        return data.url || null;
    } catch {
        // Error logged by caller
        return null;
    }
}

// ============================================================================
// TWILIO SMS
// ============================================================================

async function sendSMS(
    to: string,
    message: string,
    twilioAccountSid: string,
    twilioAuthToken: string,
    twilioFromNumber: string
): Promise<boolean> {
    if (!twilioAccountSid || !twilioAuthToken || !to) {
        return false;
    }

    try {
        const response = await fetch(
            `https://api.twilio.com/2010-04-01/Accounts/${twilioAccountSid}/Messages.json`,
            {
                method: 'POST',
                headers: {
                    Authorization: `Basic ${btoa(`${twilioAccountSid}:${twilioAuthToken}`)}`,
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: new URLSearchParams({
                    To: to,
                    From: twilioFromNumber,
                    Body: message
                })
            }
        );

        return response.ok;
    } catch {
        // Error logged by caller
        return false;
    }
}

// ============================================================================
// MAIN HANDLER
// ============================================================================

Deno.serve(async (req) => {
    // Create logger for this request
    const log = createLogger({ functionName: 'elevenlabs-webhook' });

    // Handle CORS preflight
    if (req.method === 'OPTIONS') {
        return new Response(null, { headers: corsHeaders });
    }

    // Only accept POST requests
    if (req.method !== 'POST') {
        log.warn('Method not allowed', { method: req.method });
        return new Response(JSON.stringify({ error: 'Method not allowed' }), {
            status: 405,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
    }

    try {
        // Get environment variables
        const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
        const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
        const webhookSecret = Deno.env.get('ELEVENLABS_WEBHOOK_SECRET') || '';
        const stripeSecretKey = Deno.env.get('STRIPE_SECRET_KEY') || '';
        const twilioAccountSid = Deno.env.get('TWILIO_ACCOUNT_SID') || '';
        const twilioAuthToken = Deno.env.get('TWILIO_AUTH_TOKEN') || '';
        const twilioFromNumber = Deno.env.get('TWILIO_FROM_NUMBER') || '';

        // Read request body
        const body = await req.text();

        // Capture all headers for debugging
        const allHeaders: Record<string, string> = {};
        req.headers.forEach((value, key) => {
            allHeaders[key] = value;
        });

        // Check for signature in multiple possible header names
        const signature =
            req.headers.get('elevenlabs-signature') ||
            req.headers.get('x-elevenlabs-signature') ||
            req.headers.get('x-webhook-signature') ||
            req.headers.get('x-signature');

        log.info('Webhook received', {
            hasSignature: !!signature,
            bodyLength: body.length,
            signatureHeader: signature ? 'present' : 'missing',
            headers: Object.keys(allHeaders).join(', ')
        });

        // Verify webhook signature (skip if no secret configured)
        if (webhookSecret) {
            // If no signature header found, log all headers for debugging
            if (!signature) {
                log.warn('No signature header found', {
                    checkedHeaders: [
                        'elevenlabs-signature',
                        'x-elevenlabs-signature',
                        'x-webhook-signature',
                        'x-signature'
                    ],
                    receivedHeaders: allHeaders
                });
            }

            const verification = await verifyWebhookSignature(signature, body, webhookSecret);
            if (!verification.verified) {
                log.error('Webhook verification failed', null, {
                    reason: verification.error,
                    signaturePresent: !!signature,
                    signaturePreview: signature ? signature.substring(0, 50) + '...' : null
                });
                return new Response(
                    JSON.stringify({
                        error: 'Unauthorized',
                        details: verification.error,
                        hint: 'Check ELEVENLABS_WEBHOOK_SECRET matches your ElevenLabs dashboard',
                        request_id: log.requestId
                    }),
                    {
                        status: 401,
                        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
                    }
                );
            }
            log.debug('Webhook signature verified');
        }

        // Parse payload
        const payload: ElevenLabsWebhookPayload = JSON.parse(body);
        
        // MODIFIED: Log using conversation_id instead of call_id
        // conversation_id is the unique identifier in ElevenLabs webhook payload
        log.info('Processing call', { 
            conversationId: payload.data.conversation_id,  // MODIFIED: Changed from payload.call_id
            agentId: payload.data.agent_id  // MODIFIED: Changed from payload.agent_id
        });

        // Initialize Supabase client with service role key
        const supabase = createClient(supabaseUrl, supabaseServiceKey);

        // MODIFIED: Generate idempotency key from conversation_id instead of call_id
        // conversation_id is unique per conversation and always present in ElevenLabs payload
        // This fixes the "elevenlabs_undefined" error we were getting before
        const idempotencyKey = `elevenlabs_${payload.data.conversation_id}`;

        // Check for duplicate webhook
        const { data: idempotencyCheck } = await supabase.rpc('check_webhook_idempotency', {
            p_idempotency_key: idempotencyKey
        });

        if (idempotencyCheck?.[0]?.already_processed) {
            log.warn('Duplicate webhook detected', {
                idempotencyKey,
                existingStatus: idempotencyCheck[0].existing_status
            });
            return new Response(
                JSON.stringify({
                    success: true,
                    message: 'Webhook already processed',
                    duplicate: true,
                    request_id: log.requestId
                }),
                {
                    status: 200,
                    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
                }
            );
        }

        // MODIFIED: Create webhook log entry using conversation_id
        const { data: webhookLogData } = await supabase.rpc('create_webhook_log', {
            p_source: 'elevenlabs',
            p_idempotency_key: idempotencyKey,
            p_payload: payload,
            p_request_id: log.requestId,
            p_call_id: payload.data.conversation_id  // MODIFIED: Changed from payload.call_id to conversation_id
        });

        const webhookLogId = webhookLogData;
        log.debug('Webhook log created', { webhookLogId });

        // Extract data
        const voiceCall = extractVoiceCallRecord(payload);
        const order = extractOrderFromTranscript(payload);

        // MODIFIED: Store voice call record using conversation_id
        // Note: Your voice_calls table should have a conversation_id column (or rename call_id column)
        const { error: callError } = await supabase.from('voice_calls').insert({
            call_id: voiceCall.conversation_id,  // MODIFIED: Using conversation_id as the unique identifier
            agent_id: voiceCall.agent_id,
            caller_number: voiceCall.caller_number,
            duration_seconds: voiceCall.duration_seconds,
            status: voiceCall.status,
            transcript: voiceCall.transcript,
            sentiment: voiceCall.sentiment,
            summary: voiceCall.summary,
            created_at: new Date().toISOString()
        });

        if (callError) {
            log.error('Error storing voice call', callError);
        } else {
            // MODIFIED: Log using conversation_id
            log.debug('Voice call stored', { conversationId: voiceCall.conversation_id });
        }

        // ====================================================================
        // LATENCY METRICS INSERTION (for latency_metrics table)
        // ====================================================================
        const latencyMetrics = extractLatencyMetrics(payload);
        
        if (latencyMetrics) {
            // Debug: Log the metrics object before insertion
            console.log('Latency metrics to insert:', JSON.stringify(latencyMetrics, null, 2));
            const { error: latencyError } = await supabase
                .from('latency_metrics')
                .insert({
                    call_id: latencyMetrics.call_id,
                    turn_number: latencyMetrics.turn_number,
                    sequence_id: latencyMetrics.sequence_id,
                    stt_provider: latencyMetrics.stt_provider,
                    stt_model: latencyMetrics.stt_model,
                    llm_provider: latencyMetrics.llm_provider,
                    llm_model: latencyMetrics.llm_model,
                    tts_provider: latencyMetrics.tts_provider,
                    tts_model: latencyMetrics.tts_model,
                    ttfb_ms: latencyMetrics.ttfb_ms,
                    end_to_end_ms: latencyMetrics.end_to_end_ms,
                    vad_duration_ms: latencyMetrics.vad_duration_ms,
                    stt_duration_ms: latencyMetrics.stt_duration_ms,
                    llm_ttfb_ms: latencyMetrics.llm_ttfb_ms,
                    tts_total_ms: latencyMetrics.tts_total_ms,
                    user_speech_duration_ms: latencyMetrics.user_speech_duration_ms,
                    agent_speech_duration_ms: latencyMetrics.agent_speech_duration_ms,
                    llm_tokens_in: latencyMetrics.llm_tokens_in,
                    llm_tokens_out: latencyMetrics.llm_tokens_out,
                    transcript_length: latencyMetrics.transcript_length,
                    response_length: latencyMetrics.response_length,
                    region: latencyMetrics.region,
                    agent_version: latencyMetrics.agent_version,
                    had_error: latencyMetrics.had_error,
                    error_component: latencyMetrics.error_component,
                    error_message: latencyMetrics.error_message,
                    metric_timestamp: latencyMetrics.metric_timestamp
                });

            if (latencyError) {
                console.error('LATENCY ERROR DETAILS:', latencyError);
                console.error('LATENCY ERROR STRINGIFIED:', JSON.stringify(latencyError, null, 2));
                log.error('Error storing latency metrics', { 
                    error: JSON.stringify(latencyError, null, 2),
                    errorType: typeof latencyError,
                    errorKeys: Object.keys(latencyError),
                    fullError: latencyError
                });
            } else {
                log.info('Latency metrics stored', { 
                    callId: latencyMetrics.call_id,
                    turnNumber: latencyMetrics.turn_number,
                    llmTtfbMs: latencyMetrics.llm_ttfb_ms,
                    endToEndMs: latencyMetrics.end_to_end_ms
                });
            }
        } else {
            log.debug('No latency metrics to store (no turns in transcript)');
        }
        // ====================================================================

        let paymentLink: string | null = null;
        let orderId: string | null = null;

        // Process order if extracted
        if (order && order.total_order_value > 0) {
            // Upsert customer
            const { data: customerData } = await supabase
                .from('customers')
                .upsert(
                    {
                        phone: order.customer_phone,
                        name: order.customer_name,
                        email: order.customer_email
                    },
                    { onConflict: 'phone' }
                )
                .select('customer_id')
                .single();

            // MODIFIED: Create order - generate order_id from conversation_id instead of call_id
            // System owner UUID for webhook-created orders
            const WEBHOOK_OWNER_UUID = 'e05e0713-6840-4dad-814d-61867ff72b95';
            const generatedOrderId = `ORD-${payload.data.conversation_id}`;  // MODIFIED: Changed from payload.call_id
            const { data: orderData, error: orderError } = await supabase
                .from('orders')
                .insert({
                    order_id: generatedOrderId,
                    owner: WEBHOOK_OWNER_UUID,
                    customer_id: customerData?.customer_id,
                    customer_name: order.customer_name,
                    customer_phone: order.customer_phone,
                    customer_email: order.customer_email,
                    order_type: order.order_type,
                    order_status: 'pending',
                    total_order_value: order.total_order_value,
                    special_instructions: order.special_instructions,
                    payment_status: order.payment_status,
                    call_id: payload.data.conversation_id,  // MODIFIED: Changed from payload.call_id to conversation_id
                    order_date: new Date().toISOString(),
                    created_at: new Date().toISOString()
                })
                .select('order_id')
                .single();

            if (orderError) {
                log.error('Error creating order', orderError);
            } else {
                orderId = orderData?.order_id;
                log.info('Order created', { orderId, totalValue: order.total_order_value });

                // Store order items
                if (order.items.length > 0 && orderId) {
                    const orderItems = order.items.map((item) => ({
                        order_id: orderId,
                        name: item.name,
                        quantity: item.quantity,
                        price: item.price
                    }));

                    await supabase.from('order_items').insert(orderItems);
                }
            }

            // Create Stripe payment link if configured
            if (stripeSecretKey && order.payment_status !== 'paid') {
                paymentLink = await createStripePaymentLink(order, stripeSecretKey);

                if (paymentLink) {
                    log.info('Payment link created', { orderId });
                    // Update order with payment link
                    if (orderId) {
                        await supabase
                            .from('orders')
                            .update({ payment_link: paymentLink })
                            .eq('order_id', orderId);
                    }
                } else {
                    log.warn('Failed to create payment link', { orderId });
                }
            }

            // Send SMS confirmation if configured
            if (twilioAccountSid && order.customer_phone) {
                const smsMessage = paymentLink
                    ? `Thank you for your order! Total: $${order.total_order_value.toFixed(2)}. Pay here: ${paymentLink}`
                    : `Thank you for your order! Total: $${order.total_order_value.toFixed(2)}. We'll contact you shortly.`;

                const smsSent = await sendSMS(
                    order.customer_phone,
                    smsMessage,
                    twilioAccountSid,
                    twilioAuthToken,
                    twilioFromNumber
                );

                if (smsSent) {
                    log.info('SMS confirmation sent', { phone: order.customer_phone });
                } else {
                    log.warn('Failed to send SMS confirmation', { phone: order.customer_phone });
                }
            }
        }

        // Update agent metrics (optional)
        // MODIFIED: Access agent_id from payload.data
        if (payload.data.agent_id) {
            await supabase.rpc('increment_agent_call_count', {
                p_agent_id: payload.data.agent_id  // MODIFIED: Changed from payload.agent_id because agent_id is under the data object.
            });
        }

        // Mark webhook as processed
        if (webhookLogId) {
            await supabase.rpc('mark_webhook_processed', {
                p_log_id: webhookLogId,
                p_order_id: orderId
            });
        }

        // MODIFIED: Log completion using conversation_id
        log.complete('success', {
            conversationId: payload.data.conversation_id,  // MODIFIED: Changed from callId: payload.call_id
            orderId,
            hasPaymentLink: !!paymentLink
        });

        // MODIFIED: Return response with conversation_id
        return new Response(
            JSON.stringify({
                success: true,
                conversation_id: payload.data.conversation_id,  // MODIFIED: Changed from call_id: payload.call_id
                order_id: orderId,
                payment_link: paymentLink,
                request_id: log.requestId
            }),
            {
                status: 200,
                headers: { ...corsHeaders, 'Content-Type': 'application/json' }
            }
        );
    } catch (error) {
        log.error('Webhook processing error', error);
        log.complete('error');

        // Try to mark webhook as failed (best effort)
        try {
            const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
            const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
            const supabase = createClient(supabaseUrl, supabaseServiceKey);

            // MODIFIED: Extract conversation_id from body for error logging
            const body = await req.clone().text();
            const payload = JSON.parse(body);
            // MODIFIED: Use conversation_id instead of call_id for idempotency key
            const idempotencyKey = `elevenlabs_${payload.data?.conversation_id}`;

            await supabase
                .from('webhook_logs')
                .update({
                    status: 'failed',
                    error_message: String(error),
                    error_details: { stack: error instanceof Error ? error.stack : null }
                })
                .eq('idempotency_key', idempotencyKey);
        } catch {
            // Ignore errors when marking webhook as failed
        }

        return new Response(
            JSON.stringify({
                error: 'Internal server error',
                details: String(error),
                request_id: log.requestId
            }),
            {
                status: 500,
                headers: { ...corsHeaders, 'Content-Type': 'application/json' }
            }
        );
    }
});
