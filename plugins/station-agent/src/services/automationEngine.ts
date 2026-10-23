import { obsService } from './obsService';
import { GameTelemetryData } from '../types/telemetry';

export interface TriggerRule {
  id: string;
  name: string;
  enabled: boolean;
  scope: 'MATCH' | 'P1' | 'P2';
  variable: 'ROUND_TIMER' | 'MATCH_STATE' | 'P1_HP' | 'P2_HP' | 'P1_DRIVE' | 'P2_DRIVE' | 'P1_COMBO' | 'P2_COMBO' | 'P1_DAMAGE' | 'P2_DAMAGE' | 'P1_PERFECT' | 'P2_PERFECT' | 'P1_SUPER' | 'P2_SUPER' | 'P1_ROUNDS' | 'P2_ROUNDS' | 'ALWAYS_TRUE';
  operator: '<' | '<=' | '==' | '>=' | '>';
  threshold: number | string; // string for MATCH_STATE
  
  actionType: 'TOGGLE_SOURCE' | 'TOGGLE_FILTER' | 'UPDATE_TEXT';
  sceneName?: string;
  sourceName: string;
  filterName?: string;
  textContent?: string;
  
  durationMode: 'WHILE_TRUE' | 'FIXED_TIME' | 'UNTIL_ROUND_END';
  durationSeconds?: number;
}

class AutomationEngine {
  // Keeps track of which rules are currently ACTIVE (meaning the action has been triggered and sent to OBS)
  private activeRules: Set<string> = new Set();
  
  // Keeps track of active timeouts for FIXED_TIME rules
  private ruleTimeouts: Map<string, ReturnType<typeof setTimeout>> = new Map();

  // Keeps track of last sent text per rule to avoid OBS websocket spam
  private lastSentTexts: Map<string, string> = new Map();

  // Evaluate all rules on every telemetry packet
  public evaluate(rules: TriggerRule[], telemetry: GameTelemetryData) {
    if (!obsService.getConnected()) return;

    for (const rule of rules) {
      if (!rule.enabled) continue;

      const isConditionMet = this.checkCondition(rule, telemetry);
      const isCurrentlyActive = this.activeRules.has(rule.id);

      if (isConditionMet && !isCurrentlyActive) {
        // Condition JUST became true
        this.triggerAction(rule, true, telemetry);
        this.activeRules.add(rule.id);

        if (rule.durationMode === 'FIXED_TIME' && rule.durationSeconds) {
          // Set a timeout to revert the action
          const timer = setTimeout(() => {
            this.triggerAction(rule, false);
            this.activeRules.delete(rule.id);
            this.ruleTimeouts.delete(rule.id);
            this.lastSentTexts.delete(rule.id);
          }, rule.durationSeconds * 1000);
          this.ruleTimeouts.set(rule.id, timer);
        }

      } else if (isConditionMet && isCurrentlyActive) {
        // Condition is STILL true, continuously update text if values changed
        if (rule.actionType === 'UPDATE_TEXT') {
          this.triggerAction(rule, true, telemetry);
        }
      } else if (!isConditionMet && isCurrentlyActive) {
        // Condition JUST became false (only applicable for WHILE_TRUE)
        if (rule.durationMode === 'WHILE_TRUE') {
          if (rule.actionType !== 'UPDATE_TEXT') {
            this.triggerAction(rule, false, telemetry);
          }
          this.activeRules.delete(rule.id);
          this.lastSentTexts.delete(rule.id);
        }
      }
      
      // Global reset for UNTIL_ROUND_END
      if (isCurrentlyActive && rule.durationMode === 'UNTIL_ROUND_END') {
        if (telemetry.matchState === 'ROUND_OVER' || telemetry.matchState === 'MATCH_OVER' || telemetry.matchState === 'IDLE' || telemetry.matchState === 'CHARACTER_SELECT_OR_MENU') {
          this.triggerAction(rule, false);
          this.activeRules.delete(rule.id);
          this.lastSentTexts.delete(rule.id);
        }
      }
    }
  }

  private checkCondition(rule: TriggerRule, data: GameTelemetryData): boolean {
    if (rule.variable === 'ALWAYS_TRUE') return true;

    let currentValue: number | string;

    switch (rule.variable) {
      case 'ROUND_TIMER': currentValue = data.roundTimer; break;
      case 'MATCH_STATE': currentValue = data.matchState; break;
      case 'P1_HP': currentValue = data.p1.currentHp; break;
      case 'P2_HP': currentValue = data.p2.currentHp; break;
      case 'P1_DRIVE': currentValue = data.p1.driveGauge; break;
      case 'P2_DRIVE': currentValue = data.p2.driveGauge; break;
      case 'P1_COMBO': currentValue = data.p1.maxCombo; break;
      case 'P2_COMBO': currentValue = data.p2.maxCombo; break;
      case 'P1_DAMAGE': currentValue = data.p1.maxDamage; break;
      case 'P2_DAMAGE': currentValue = data.p2.maxDamage; break;
      case 'P1_PERFECT': currentValue = (data.matchState === 'ROUND_OVER' && data.p1.currentHp === data.p1.maxHp && data.p1.currentHp > 0) ? 1 : 0; break;
      case 'P2_PERFECT': currentValue = (data.matchState === 'ROUND_OVER' && data.p2.currentHp === data.p2.maxHp && data.p2.currentHp > 0) ? 1 : 0; break;
      case 'P1_SUPER': currentValue = data.p1.superArt; break;
      case 'P2_SUPER': currentValue = data.p2.superArt; break;
      case 'P1_ROUNDS': currentValue = data.p1.roundsWon; break;
      case 'P2_ROUNDS': currentValue = data.p2.roundsWon; break;
      default: return false;
    }

    if (rule.operator === '==') return currentValue == rule.threshold;
    if (typeof currentValue === 'number' && typeof rule.threshold === 'number') {
      switch (rule.operator) {
        case '<': return currentValue < rule.threshold;
        case '<=': return currentValue <= rule.threshold;
        case '>': return currentValue > rule.threshold;
        case '>=': return currentValue >= rule.threshold;
      }
    }

    return false;
  }

  public parseTextTemplate(template: string, telemetry: GameTelemetryData): string {
    let result = template;
    const replacements: Record<string, string | number> = {
      '[P1_Name]': telemetry.p1.displayName || telemetry.p1.characterName || 'P1',
      '[P2_Name]': telemetry.p2.displayName || telemetry.p2.characterName || 'P2',
      '[P1_Character]': telemetry.p1.characterName || 'Unknown',
      '[P2_Character]': telemetry.p2.characterName || 'Unknown',
      '[P1_Score]': telemetry.p1.scoreInSet || 0,
      '[P2_Score]': telemetry.p2.scoreInSet || 0,
      '[P1_Rounds]': telemetry.p1.roundsWon || 0,
      '[P2_Rounds]': telemetry.p2.roundsWon || 0,
      '[P1_HP]': telemetry.p1.currentHp || 0,
      '[P2_HP]': telemetry.p2.currentHp || 0,
      '[Round_Timer]': telemetry.roundTimer || 99,
      '[Match_State]': telemetry.matchState || 'IDLE'
    };

    for (const [key, value] of Object.entries(replacements)) {
      // Replace all occurrences, case insensitive
      const regex = new RegExp(key.replace(/\[/g, '\\[').replace(/\]/g, '\\]'), 'gi');
      result = result.replace(regex, String(value));
    }
    return result;
  }

  public triggerAction(rule: TriggerRule, enable: boolean, telemetry?: GameTelemetryData) {
    if (rule.actionType === 'TOGGLE_SOURCE') {
      const targetScene = rule.sceneName || obsService.getCurrentScene();
      if (targetScene && rule.sourceName) {
        obsService.toggleSource(targetScene, rule.sourceName, enable);
      }
    } else if (rule.actionType === 'TOGGLE_FILTER' && rule.filterName) {
      obsService.toggleFilter(rule.sourceName, rule.filterName, enable);
    } else if (rule.actionType === 'UPDATE_TEXT' && rule.textContent && telemetry && enable) {
      const parsedText = this.parseTextTemplate(rule.textContent, telemetry);
      const prevText = this.lastSentTexts.get(rule.id);
      
      // Only send WebSocket request if the text actually changed to prevent OBS spam
      if (parsedText !== prevText) {
        obsService.setInputSettings(rule.sourceName, { text: parsedText });
        this.lastSentTexts.set(rule.id, parsedText);
      }
    }
  }
}

export const automationEngine = new AutomationEngine();
