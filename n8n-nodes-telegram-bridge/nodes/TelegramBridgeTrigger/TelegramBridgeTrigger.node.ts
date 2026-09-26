import type {
	IDataObject,
	IWebhookFunctions,
	IWebhookResponseData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes } from 'n8n-workflow';

export class TelegramBridgeTrigger implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Telegram Bridge Trigger',
		name: 'telegramBridgeTrigger',
		icon: 'file:icon.svg',
		group: ['trigger'],
		version: 1,
		description:
			"Starts the workflow when the telegram_bridge long-polling service forwards a Telegram update. No public HTTPS webhook required — this only ever receives localhost traffic from the bridge. Output matches the built-in Telegram Trigger node's shape exactly (the raw Telegram Update object), so expressions like {{$json.message.chat.id}} work the same.",
		defaults: {
			name: 'Telegram Bridge Trigger',
		},
		inputs: [],
		outputs: [NodeConnectionTypes.Main],
		webhooks: [
			{
				name: 'default',
				httpMethod: 'POST',
				responseMode: 'onReceived',
				path: '={{$parameter["path"]}}',
			},
		],
		properties: [
			{
				displayName: 'Path',
				name: 'path',
				type: 'string',
				default: 'telegram-in',
				required: true,
				description:
					"The webhook path to listen on. The bridge's N8N_WEBHOOK_URL must point at this same path, e.g. http://localhost:5678/webhook/telegram-in.",
			},
		],
	};

	async webhook(this: IWebhookFunctions): Promise<IWebhookResponseData> {
		const bodyData = this.getBodyData() as IDataObject;

		return {
			workflowData: [this.helpers.returnJsonArray(bodyData)],
		};
	}
}
