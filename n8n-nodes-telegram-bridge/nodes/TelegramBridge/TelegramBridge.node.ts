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
		description:
			'Send/edit Telegram messages via the self-hosted long-polling bridge (drop-in for the built-in Telegram node\'s send side)',
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
						description: 'Send a text message',
						action: 'Send a text message',
					},
					{
						name: 'Send Photo',
						value: 'sendPhoto',
						description: 'Send a photo, with an optional caption',
						action: 'Send a photo',
					},
					{
						name: 'Send Document',
						value: 'sendDocument',
						description: 'Send a document/file, with an optional caption',
						action: 'Send a document',
					},
					{
						name: 'Edit Message Text',
						value: 'editMessageText',
						description: 'Edit the text of a message the bot previously sent',
						action: 'Edit a message',
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
				description: 'Telegram chat ID to send/edit the message in',
			},
			{
				displayName: 'Message ID',
				name: 'messageId',
				type: 'string',
				default: '',
				required: true,
				displayOptions: {
					show: {
						operation: ['editMessageText'],
					},
				},
				description: 'ID of the message to edit (e.g. from the incoming update\'s message.message_id)',
			},
			{
				displayName: 'Text',
				name: 'text',
				type: 'string',
				typeOptions: {
					rows: 3,
				},
				default: '',
				required: true,
				displayOptions: {
					show: {
						operation: ['sendMessage', 'editMessageText'],
					},
				},
				description: 'Text of the message',
			},
			{
				displayName: 'Photo Path',
				name: 'photoPath',
				type: 'string',
				default: '',
				required: true,
				displayOptions: {
					show: {
						operation: ['sendPhoto'],
					},
				},
				description: 'Local filesystem path (on the bridge host) of the photo to send',
			},
			{
				displayName: 'Document Path',
				name: 'documentPath',
				type: 'string',
				default: '',
				required: true,
				displayOptions: {
					show: {
						operation: ['sendDocument'],
					},
				},
				description: 'Local filesystem path (on the bridge host) of the document to send',
			},
			{
				displayName: 'Caption',
				name: 'caption',
				type: 'string',
				default: '',
				displayOptions: {
					show: {
						operation: ['sendPhoto', 'sendDocument'],
					},
				},
				description: 'Optional caption for the photo/document',
			},
			{
				displayName: 'Additional Fields',
				name: 'additionalFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				options: [
					{
						displayName: 'Parse Mode',
						name: 'parseMode',
						type: 'options',
						options: [
							{ name: 'None', value: '' },
							{ name: 'Markdown', value: 'Markdown' },
							{ name: 'MarkdownV2', value: 'MarkdownV2' },
							{ name: 'HTML', value: 'HTML' },
						],
						default: '',
						description: 'How Telegram should parse the text/caption for formatting',
					},
					{
						displayName: 'Disable Notification',
						name: 'disableNotification',
						type: 'boolean',
						default: false,
						description: 'Whether to send the message silently',
						displayOptions: {
							hide: {
								'/operation': ['editMessageText'],
							},
						},
					},
					{
						displayName: 'Reply To Message ID',
						name: 'replyToMessageId',
						type: 'string',
						default: '',
						description: 'Make this message a reply to another message in the chat',
						displayOptions: {
							hide: {
								'/operation': ['editMessageText'],
							},
						},
					},
					{
						displayName: 'Reply Markup (Inline Keyboard JSON)',
						name: 'replyMarkup',
						type: 'json',
						default: '',
						description:
							'Telegram inline keyboard as JSON, e.g. {"inline_keyboard":[[{"text":"Yes","callback_data":"yes"}]]}',
					},
				],
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
				const operation = this.getNodeParameter('operation', itemIndex) as string;
				const chatId = this.getNodeParameter('chatId', itemIndex) as string;
				const additionalFields = this.getNodeParameter(
					'additionalFields',
					itemIndex,
					{},
				) as IDataObject;

				const body: IDataObject = { operation, chat_id: chatId };

				if (operation === 'sendMessage' || operation === 'editMessageText') {
					body.text = this.getNodeParameter('text', itemIndex) as string;
				}
				if (operation === 'editMessageText') {
					body.message_id = this.getNodeParameter('messageId', itemIndex) as string;
				}
				if (operation === 'sendPhoto') {
					const photoPath = this.getNodeParameter('photoPath', itemIndex) as string;
					if (!photoPath) {
						throw new NodeOperationError(this.getNode(), 'Photo Path is required', {
							itemIndex,
						});
					}
					body.photo_path = photoPath;
				}
				if (operation === 'sendDocument') {
					const documentPath = this.getNodeParameter('documentPath', itemIndex) as string;
					if (!documentPath) {
						throw new NodeOperationError(this.getNode(), 'Document Path is required', {
							itemIndex,
						});
					}
					body.document_path = documentPath;
				}
				if (operation === 'sendPhoto' || operation === 'sendDocument') {
					const caption = this.getNodeParameter('caption', itemIndex, '') as string;
					if (caption) {
						body.caption = caption;
					}
				}

				if (additionalFields.parseMode) {
					body.parse_mode = additionalFields.parseMode;
				}
				if (
					additionalFields.disableNotification !== undefined &&
					operation !== 'editMessageText'
				) {
					body.disable_notification = additionalFields.disableNotification;
				}
				if (additionalFields.replyToMessageId && operation !== 'editMessageText') {
					body.reply_to_message_id = additionalFields.replyToMessageId;
				}
				if (additionalFields.replyMarkup) {
					const raw = additionalFields.replyMarkup;
					body.reply_markup = typeof raw === 'string' ? JSON.parse(raw) : raw;
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
