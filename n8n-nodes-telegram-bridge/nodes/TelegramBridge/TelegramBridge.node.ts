import type {
	IDataObject,
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';

export class TelegramBridge implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Telegram Bridge',
		name: 'telegramBridge',
		icon: 'file:icon.svg',
		group: ['output'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Send Telegram messages via the self-hosted long-polling bridge',
		defaults: {
			name: 'Telegram Bridge',
		},
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [
			{
				name: 'telegramBridgeApi',
				required: true,
			},
		],
		properties: [
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				options: [
					{
						name: 'Send Message',
						value: 'sendMessage',
						description: 'Send a text message or a photo through the bridge',
						action: 'Send a message',
					},
				],
				default: 'sendMessage',
			},
			{
				displayName: 'Chat ID',
				name: 'chatId',
				type: 'string',
				default: '',
				required: true,
				description: 'Telegram chat ID to send the message to',
			},
			{
				displayName: 'Send Photo',
				name: 'sendPhoto',
				type: 'boolean',
				default: false,
				description: 'Whether to send a photo (with optional caption) instead of plain text',
			},
			{
				displayName: 'Message Text',
				name: 'text',
				type: 'string',
				typeOptions: {
					rows: 3,
				},
				default: '',
				displayOptions: {
					show: {
						sendPhoto: [false],
					},
				},
				description: 'Text of the message to send',
			},
			{
				displayName: 'Photo Path',
				name: 'photoPath',
				type: 'string',
				default: '',
				displayOptions: {
					show: {
						sendPhoto: [true],
					},
				},
				description: 'Local filesystem path (on the bridge host) of the photo to send',
			},
			{
				displayName: 'Caption',
				name: 'caption',
				type: 'string',
				default: '',
				displayOptions: {
					show: {
						sendPhoto: [true],
					},
				},
				description: 'Optional caption for the photo',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const credentials = await this.getCredentials('telegramBridgeApi');
		const baseUrl = ((credentials.baseUrl as string) || 'http://127.0.0.1:8811').replace(
			/\/+$/,
			'',
		);

		for (let itemIndex = 0; itemIndex < items.length; itemIndex++) {
			try {
				const chatId = this.getNodeParameter('chatId', itemIndex) as string;
				const sendPhoto = this.getNodeParameter('sendPhoto', itemIndex) as boolean;

				const body: IDataObject = { chat_id: chatId };

				if (sendPhoto) {
					const photoPath = this.getNodeParameter('photoPath', itemIndex) as string;
					const caption = this.getNodeParameter('caption', itemIndex) as string;
					if (!photoPath) {
						throw new NodeOperationError(this.getNode(), 'Photo Path is required when Send Photo is enabled', {
							itemIndex,
						});
					}
					body.photo_path = photoPath;
					if (caption) {
						body.caption = caption;
					}
				} else {
					const text = this.getNodeParameter('text', itemIndex) as string;
					if (!text) {
						throw new NodeOperationError(this.getNode(), 'Message Text is required', {
							itemIndex,
						});
					}
					body.text = text;
				}

				const response = await this.helpers.httpRequest({
					method: 'POST',
					url: `${baseUrl}/send`,
					body,
					json: true,
				});

				returnData.push({
					json: response as IDataObject,
					pairedItem: { item: itemIndex },
				});
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: (error as Error).message },
						pairedItem: { item: itemIndex },
					});
					continue;
				}
				throw error;
			}
		}

		return [returnData];
	}
}
