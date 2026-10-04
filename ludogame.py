from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass

import pygame


WINDOW_SIZE = (1180, 800)
PLAYER_STARTS = (0, 13, 26, 39)
SAFE_SPACES = frozenset((0, 8, 13, 21, 26, 34, 39, 47))

MAIN_PATH = (
	[(6, column) for column in range(1, 6)]
	+ [(row, 6) for row in range(5, -1, -1)]
	+ [(0, column) for column in range(7, 9)]
	+ [(row, 8) for row in range(1, 6)]
	+ [(6, column) for column in range(9, 15)]
	+ [(row, 14) for row in range(7, 9)]
	+ [(8, column) for column in range(13, 8, -1)]
	+ [(row, 8) for row in range(9, 15)]
	+ [(14, column) for column in range(7, 5, -1)]
	+ [(row, 6) for row in range(13, 8, -1)]
	+ [(8, column) for column in range(5, -1, -1)]
	+ [(row, 0) for row in range(7, 5, -1)]
)

HOME_LANES = (
	[(7, column) for column in range(2, 7)],
	[(row, 7) for row in range(2, 7)],
	[(7, column) for column in range(12, 7, -1)],
	[(row, 7) for row in range(12, 7, -1)],
)

YARD_POSITIONS = (
	((1, 1), (1, 4), (4, 1), (4, 4)),
	((1, 10), (1, 13), (4, 10), (4, 13)),
	((10, 10), (10, 13), (13, 10), (13, 13)),
	((10, 1), (10, 4), (13, 1), (13, 4)),
)


@dataclass(frozen=True)
class Player:
	name: str
	color: tuple[int, int, int]
	pale: tuple[int, int, int]
	start: int


PLAYERS = (
	Player("Ruby", (211, 69, 65), (250, 226, 222), PLAYER_STARTS[0]),
	Player("Jade", (43, 130, 101), (221, 241, 231), PLAYER_STARTS[1]),
	Player("Gold", (218, 159, 47), (250, 240, 208), PLAYER_STARTS[2]),
	Player("Azure", (56, 117, 174), (224, 236, 248), PLAYER_STARTS[3]),
)


def shade_color(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
	return tuple(max(0, min(255, round(channel * factor))) for channel in color)


def build_track_arrows() -> dict[int, tuple[tuple[int, int], int | None]]:
	arrows: dict[int, tuple[tuple[int, int], int | None]] = {}
	for index, current in enumerate(MAIN_PATH):
		previous = MAIN_PATH[index - 1]
		next_position = MAIN_PATH[(index + 1) % len(MAIN_PATH)]
		incoming = (current[0] - previous[0], current[1] - previous[1])
		outgoing = (next_position[0] - current[0], next_position[1] - current[1])
		if incoming != outgoing:
			arrows[index] = (outgoing, None)

	for player_index, player in enumerate(PLAYERS):
		entry_index = (player.start - 1) % len(MAIN_PATH)
		entry = MAIN_PATH[entry_index]
		lane_entry = HOME_LANES[player_index][0]
		direction = (lane_entry[0] - entry[0], lane_entry[1] - entry[1])
		arrows[entry_index] = (direction, player_index)
	return arrows


TRACK_ARROWS = build_track_arrows()


class LudoGame:
	def __init__(self, player_count: int = 4) -> None:
		self.rng = random.Random()
		self.new_game(player_count)

	def new_game(self, player_count: int = 4) -> None:
		if player_count not in (2, 3, 4):
			raise ValueError("Ludo supports 2, 3, or 4 players.")
		self.player_count = player_count
		self.active_players = (0, 2) if player_count == 2 else tuple(range(player_count))
		self.tokens = [[-1] * 4 for _ in PLAYERS]
		self.turn_cursor = 0
		self.die_value: int | None = None
		self.last_roll: int | None = None
		self.legal_tokens: set[int] = set()
		self.winner: int | None = None
		self.message = f"{self.current_player.name} starts. Roll the die."

	@property
	def current_player_index(self) -> int:
		return self.active_players[self.turn_cursor]

	@property
	def current_player(self) -> Player:
		return PLAYERS[self.current_player_index]

	def _legal_tokens(self, player_index: int, roll: int) -> set[int]:
		legal = set()
		for token_index, progress in enumerate(self.tokens[player_index]):
			if progress == -1:
				if roll == 6:
					legal.add(token_index)
			elif progress + roll <= 57:
				legal.add(token_index)
		return legal

	def roll(self) -> int | None:
		if self.winner is not None or self.die_value is not None:
			return None

		roll = self.rng.randint(1, 6)
		self.die_value = roll
		self.last_roll = roll
		self.legal_tokens = self._legal_tokens(self.current_player_index, roll)
		player = self.current_player

		if self.legal_tokens:
			self.message = f"{player.name} rolled {roll}. Choose a highlighted pawn."
		else:
			self.die_value = None
			self.message = f"{player.name} rolled {roll}; no pawn can move."
			if roll != 6:
				self._advance_turn()
		return roll

	def move_token(self, token_index: int) -> bool:
		if self.die_value is None or token_index not in self.legal_tokens:
			return False

		player_index = self.current_player_index
		player = PLAYERS[player_index]
		roll = self.die_value
		progress = self.tokens[player_index][token_index]
		self.tokens[player_index][token_index] = 0 if progress == -1 else progress + roll
		landing = self.tokens[player_index][token_index]
		captured = 0

		if landing < 52:
			global_space = (player.start + landing) % len(MAIN_PATH)
			if global_space not in SAFE_SPACES:
				for opponent_index in self.active_players:
					if opponent_index == player_index:
						continue
					for opponent_token, opponent_progress in enumerate(self.tokens[opponent_index]):
						if (
							0 <= opponent_progress < 52
							and (PLAYERS[opponent_index].start + opponent_progress) % len(MAIN_PATH)
							== global_space
						):
							self.tokens[opponent_index][opponent_token] = -1
							captured += 1

		self.die_value = None
		self.legal_tokens.clear()

		if all(position == 57 for position in self.tokens[player_index]):
			self.winner = player_index
			self.message = f"{player.name} wins the race!"
			return True

		details = f"{player.name} moved pawn {token_index + 1}."
		if captured:
			details += f" Captured {captured} pawn{'s' if captured != 1 else ''}."
		if roll == 6:
			self.message = f"{details} Roll again."
		else:
			self.message = details
			self._advance_turn()
		return True

	def _advance_turn(self) -> None:
		self.turn_cursor = (self.turn_cursor + 1) % len(self.active_players)


class LudoApp:
	BACKGROUND = (242, 243, 237)
	INK = (34, 42, 38)
	MUTED = (111, 120, 113)
	WHITE = (255, 255, 252)
	LINE = (222, 225, 216)
	BOARD = (232, 234, 225)
	DARK = (50, 58, 52)
	ARROW = (151, 159, 151)

	def __init__(self) -> None:
		pygame.init()
		pygame.display.set_caption("Ludo Club | Pass & Play")
		self.screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
		self.clock = pygame.time.Clock()
		self.game = LudoGame()
		self.fonts = {
			size: pygame.font.SysFont("DejaVu Sans", size, bold=bold)
			for size, bold in ((13, False), (15, False), (16, True), (18, True), (23, True), (32, True), (42, True))
		}
		self.board_rect = pygame.Rect(0, 0, 0, 0)
		self.roll_rect = pygame.Rect(0, 0, 0, 0)
		self.new_game_rect = pygame.Rect(0, 0, 0, 0)
		self.player_count_rects: dict[int, pygame.Rect] = {}
		self.token_hits: list[tuple[pygame.Vector2, int, int, float]] = []
		self.animation_time = 0.0

	def run(self) -> None:
		running = True
		while running:
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					running = False
				elif event.type == pygame.VIDEORESIZE:
					self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
				elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
					self.handle_click(event.pos)
				elif event.type == pygame.KEYDOWN:
					if event.key == pygame.K_ESCAPE:
						running = False
					elif event.key == pygame.K_r:
						self.game.roll()
					elif event.key == pygame.K_n:
						self.game.new_game(self.game.player_count)
					elif pygame.K_1 <= event.key <= pygame.K_4:
						self.game.move_token(event.key - pygame.K_1)

			self.draw()
			pygame.display.flip()
			self.animation_time += self.clock.tick(60) / 1000

		pygame.quit()
		sys.exit()

	def handle_click(self, point: tuple[int, int]) -> None:
		if self.new_game_rect.collidepoint(point):
			self.game.new_game(self.game.player_count)
			return
		for count, rect in self.player_count_rects.items():
			if rect.collidepoint(point):
				self.game.new_game(count)
				return
		if self.roll_rect.collidepoint(point):
			self.game.roll()
			return

		if self.game.die_value is None:
			return
		for center, player_index, token_index, radius in reversed(self.token_hits):
			if player_index != self.game.current_player_index or token_index not in self.game.legal_tokens:
				continue
			if center.distance_to(point) <= radius + 4:
				self.game.move_token(token_index)
				return

	def draw(self) -> None:
		width, height = self.screen.get_size()
		self.screen.fill(self.BACKGROUND)
		self.draw_header()

		margin = 28
		top = 94
		sidebar_width = 330
		gap = 24
		board_size = min(height - top - 28, width - margin * 2 - sidebar_width - gap)
		board_size = max(360, board_size)
		self.board_rect = pygame.Rect(margin, top, board_size, board_size)
		self.draw_board(self.board_rect)

		side_x = self.board_rect.right + gap
		side_width = max(300, width - side_x - margin)
		self.draw_sidebar(pygame.Rect(side_x, top, side_width, board_size))

	def draw_header(self) -> None:
		self.text("LUDO CLUB", 18, self.INK, (30, 23))
		self.text("PASS & PLAY", 13, self.MUTED, (30, 51))
		width = self.screen.get_width()
		self.text("A little luck. A lot of racing.", 15, self.MUTED, (width - 285, 34))
		pygame.draw.line(self.screen, self.LINE, (28, 78), (width - 28, 78), 1)

	def draw_board(self, rect: pygame.Rect) -> None:
		pygame.draw.rect(self.screen, self.WHITE, rect, border_radius=22)
		inset = max(9, rect.width * 0.018)
		cell = (rect.width - inset * 2) / 15
		origin_x = rect.x + inset
		origin_y = rect.y + inset

		def cell_rect(position: tuple[int, int], pad: float = 2.2) -> pygame.Rect:
			row, column = position
			return pygame.Rect(
				round(origin_x + column * cell + pad),
				round(origin_y + row * cell + pad),
				round(cell - pad * 2),
				round(cell - pad * 2),
			)

		for player_index, zone in enumerate(((0, 0), (0, 9), (9, 9), (9, 0))):
			row, column = zone
			zone_rect = pygame.Rect(
				round(origin_x + column * cell + 2),
				round(origin_y + row * cell + 2),
				round(cell * 6 - 4),
				round(cell * 6 - 4),
			)
			player = PLAYERS[player_index]
			pygame.draw.rect(self.screen, player.pale, zone_rect, border_radius=round(cell * 0.35))
			inner = zone_rect.inflate(-cell * 1.15, -cell * 1.15)
			pygame.draw.rect(self.screen, self.WHITE, inner, border_radius=round(cell * 0.3))
			pygame.draw.rect(self.screen, player.color, inner, width=2, border_radius=round(cell * 0.3))
			for position in YARD_POSITIONS[player_index]:
				slot_center = (
					round(origin_x + (position[1] + 0.5) * cell),
					round(origin_y + (position[0] + 0.5) * cell),
				)
				slot_radius = max(3, round(cell * 0.42))
				pygame.draw.circle(self.screen, player.pale, slot_center, slot_radius)
				pygame.draw.circle(self.screen, player.color, slot_center, slot_radius, width=1)
			self.draw_home_logo(
				(origin_x + (column + 3) * cell, origin_y + (row + 3) * cell),
				cell,
				player,
			)

		for player_index, lane in enumerate(HOME_LANES):
			player = PLAYERS[player_index]
			for position in lane:
				tile = cell_rect(position, 2.7)
				pygame.draw.rect(self.screen, player.pale, tile, border_radius=5)
				pygame.draw.rect(self.screen, player.color, tile, width=1, border_radius=5)

		for path_index, position in enumerate(MAIN_PATH):
			tile = cell_rect(position, 2.7)
			pygame.draw.rect(self.screen, self.WHITE, tile, border_radius=5)
			pygame.draw.rect(self.screen, self.LINE, tile, width=1, border_radius=5)
			arrow = TRACK_ARROWS.get(path_index)
			if arrow is not None:
				direction, home_player = arrow
				arrow_color = shade_color(PLAYERS[home_player].color, 0.72) if home_player is not None else self.ARROW
				self.draw_track_arrow(tile, direction, cell, arrow_color)
			if path_index in PLAYER_STARTS:
				player = PLAYERS[PLAYER_STARTS.index(path_index)]
				pygame.draw.rect(self.screen, player.color, tile, border_radius=5)
				pygame.draw.circle(self.screen, self.WHITE, tile.center, max(2, int(cell * 0.08)))
			elif path_index in SAFE_SPACES:
				pygame.draw.circle(self.screen, (172, 179, 164), tile.center, max(2, int(cell * 0.075)))

		self.draw_center(cell, origin_x, origin_y)
		self.draw_tokens(cell, origin_x, origin_y)

	def draw_track_arrow(
		self,
		tile: pygame.Rect,
		direction: tuple[int, int],
		cell: float,
		color: tuple[int, int, int],
	) -> None:
		vector = pygame.Vector2(direction[1], direction[0])
		if vector.length_squared() == 0:
			return
		vector.normalize_ip()
		perpendicular = pygame.Vector2(-vector.y, vector.x)
		center = pygame.Vector2(tile.center) + vector * cell * 0.16
		tip = center + vector * cell * 0.16
		head_base = center - vector * cell * 0.025
		shaft_start = center - vector * cell * 0.16
		half_width = cell * 0.075
		pygame.draw.line(self.screen, color, shaft_start, head_base, max(1, round(cell * 0.045)))
		pygame.draw.polygon(
			self.screen,
			color,
			(tip, head_base + perpendicular * half_width, head_base - perpendicular * half_width),
		)

	def draw_home_logo(self, center: tuple[float, float], cell: float, player: Player) -> None:
		center_x, center_y = round(center[0]), round(center[1])
		die_size = max(12, round(cell * 0.52))
		gap = max(2, round(cell * 0.08))
		pawn_width = max(8, round(cell * 0.30))
		pawn_height = max(14, round(cell * 0.52))
		total_width = die_size + gap + pawn_width
		left = round(center_x - total_width / 2)
		top = round(center_y - cell * 0.39)
		die_rect = pygame.Rect(left, top, die_size, die_size)
		pygame.draw.rect(
			self.screen,
			shade_color(player.color, 0.72),
			die_rect.inflate(2, 2),
			border_radius=max(3, round(cell * 0.08)),
		)
		pygame.draw.rect(
			self.screen,
			player.color,
			die_rect,
			border_radius=max(3, round(cell * 0.08)),
		)
		pip_radius = max(1, round(die_size * 0.055))
		for dx, dy in ((0.28, 0.28), (0.72, 0.28), (0.5, 0.5), (0.28, 0.72), (0.72, 0.72)):
			pip = (round(left + die_size * dx), round(top + die_size * dy))
			pygame.draw.circle(self.screen, player.pale, pip, pip_radius)

		pawn_x = round(left + die_size + gap + pawn_width / 2)
		base_y = top + die_size
		head_radius = max(2, round(cell * 0.09))
		head_center = (pawn_x, top + head_radius + 1)
		body_top = head_center[1] + head_radius - 1
		body_half_top = max(2, round(pawn_width * 0.22))
		body_half_bottom = max(3, round(pawn_width * 0.43))
		body_bottom = base_y - 2
		pygame.draw.ellipse(
			self.screen,
			shade_color(player.color, 0.68),
			pygame.Rect(pawn_x - pawn_width // 2, base_y - 5, pawn_width, 6),
		)
		pygame.draw.polygon(
			self.screen,
			player.color,
			(
				(pawn_x - body_half_top, body_top),
				(pawn_x + body_half_top, body_top),
				(pawn_x + body_half_bottom, body_bottom),
				(pawn_x - body_half_bottom, body_bottom),
			),
		)
		pygame.draw.circle(self.screen, shade_color(player.color, 0.7), head_center, head_radius + 1)
		pygame.draw.circle(self.screen, player.color, head_center, head_radius)
		pygame.draw.circle(
			self.screen,
			player.pale,
			(head_center[0] - 1, head_center[1] - 1),
			max(1, head_radius // 3),
		)

		label_size = max(8, round(cell * 0.17))
		label_font = self.fonts.get(label_size)
		if label_font is None:
			label_font = pygame.font.SysFont("DejaVu Sans", label_size, bold=True)
			self.fonts[label_size] = label_font
		label = label_font.render("LUDO", True, shade_color(player.color, 0.78))
		self.screen.blit(label, label.get_rect(center=(center_x, round(center_y + cell * 0.31))))

	def draw_center(self, cell: float, origin_x: float, origin_y: float) -> None:
		left = origin_x + 6 * cell
		top = origin_y + 6 * cell
		right = left + 3 * cell
		bottom = top + 3 * cell
		center = (round(left + 1.5 * cell), round(top + 1.5 * cell))
		triangles = (
			(PLAYERS[0].color, ((left, top), (left, bottom), center)),
			(PLAYERS[1].color, ((left, top), (right, top), center)),
			(PLAYERS[2].color, ((right, top), (right, bottom), center)),
			(PLAYERS[3].color, ((left, bottom), (right, bottom), center)),
		)
		for color, points in triangles:
			pygame.draw.polygon(self.screen, color, points)
		pygame.draw.circle(self.screen, self.WHITE, center, max(3, round(cell * 0.15)))
		pygame.draw.circle(self.screen, self.DARK, center, max(2, round(cell * 0.055)))

	def draw_tokens(self, cell: float, origin_x: float, origin_y: float) -> None:
		self.token_hits.clear()
		occupied: dict[tuple[int, int], list[tuple[int, int, bool]]] = {}
		finished: list[tuple[int, int]] = []

		for player_index in self.game.active_players:
			for token_index, progress in enumerate(self.game.tokens[player_index]):
				if progress == -1:
					position = YARD_POSITIONS[player_index][token_index]
				elif progress < 52:
					position = MAIN_PATH[(PLAYERS[player_index].start + progress) % len(MAIN_PATH)]
				elif progress < 57:
					position = HOME_LANES[player_index][progress - 52]
				else:
					finished.append((player_index, token_index))
					continue
				occupied.setdefault(position, []).append(
					(player_index, token_index, token_index in self.game.legal_tokens and player_index == self.game.current_player_index)
				)

		for position, tokens in occupied.items():
			x = origin_x + (position[1] + 0.5) * cell
			y = origin_y + (position[0] + 0.5) * cell
			offsets = ((-0.14, -0.12), (0.14, -0.12), (-0.14, 0.12), (0.14, 0.12))
			stack = sorted(enumerate(tokens), key=lambda item: offsets[item[0]][1])
			piece_scale = 0.76 if len(tokens) > 1 else 1.0
			for stack_index, (player_index, token_index, legal) in stack:
				offset = offsets[stack_index] if len(tokens) > 1 else (0, 0)
				center = pygame.Vector2(x + offset[0] * cell, y + offset[1] * cell)
				lift = 0.0
				if legal:
					lift = cell * 0.07 * (0.5 + 0.5 * math.sin(self.animation_time * 6 + token_index * 0.8))
				self.draw_token(center, cell, PLAYERS[player_index], legal, token_index + 1, piece_scale, lift)
				hit_center = pygame.Vector2(center.x, center.y - cell * 0.5 * piece_scale - lift)
				self.token_hits.append((hit_center, player_index, token_index, cell * 0.48 * piece_scale))

		center_x = origin_x + 7.5 * cell
		center_y = origin_y + 7.5 * cell
		finish_offsets = ((-0.16, -0.12), (0.16, -0.12), (-0.16, 0.12), (0.16, 0.12))
		finish_stack = [
			(
				player_index,
				token_index,
				pygame.Vector2(
					center_x + finish_offsets[token_index][0] * cell,
					center_y + finish_offsets[token_index][1] * cell,
				),
			)
			for player_index, token_index in finished
		]
		for player_index, token_index, center in sorted(finish_stack, key=lambda item: item[2].y):
			self.draw_token(center, cell, PLAYERS[player_index], False, token_index + 1, 0.76)

	def draw_token(
		self,
		center: pygame.Vector2,
		cell: float,
		player: Player,
		legal: bool,
		label: int,
		scale: float = 1.0,
		lift: float = 0.0,
	) -> None:
		piece_cell = cell * scale
		ground_point = (round(center.x), round(center.y))
		shadow_width = max(18, round(piece_cell * 0.78))
		shadow_height = max(9, round(piece_cell * 0.22))
		shadow = pygame.Surface((shadow_width, shadow_height), pygame.SRCALPHA)
		for inset, alpha in ((0, 12), (2, 18), (4, 25)):
			shadow_rect = pygame.Rect(inset, inset // 2, shadow_width - inset * 2, shadow_height - inset)
			pygame.draw.ellipse(shadow, (25, 34, 28, alpha), shadow_rect)
		self.screen.blit(shadow, (ground_point[0] - shadow_width // 2, ground_point[1] - shadow_height // 2 + 1))

		if legal:
			halo = pygame.Rect(
				round(ground_point[0] - piece_cell * 0.46),
				round(ground_point[1] - piece_cell * 0.15),
				round(piece_cell * 0.92),
				round(piece_cell * 0.30),
			)
			pygame.draw.ellipse(self.screen, (255, 255, 252), halo, width=2)
			pygame.draw.ellipse(self.screen, (38, 47, 40), halo.inflate(-3, -2), width=1)

		sprite_width = max(16, round(piece_cell * 0.78))
		sprite_height = max(24, round(piece_cell * 1.02))
		sprite = pygame.Surface((sprite_width, sprite_height), pygame.SRCALPHA)
		sprite_center_x = sprite_width // 2
		sprite_base_y = sprite_height - 2
		dark_color = shade_color(player.color, 0.48)
		light_color = shade_color(player.color, 1.24)

		base_width = max(12, round(piece_cell * 0.62))
		base_height = max(6, round(piece_cell * 0.19))
		base_rect = pygame.Rect(
			sprite_center_x - base_width // 2,
			sprite_base_y - base_height,
			base_width,
			base_height,
		)
		pygame.draw.ellipse(sprite, dark_color, base_rect)
		base_inner = base_rect.inflate(-2, -2)
		if base_inner.width > 0 and base_inner.height > 0:
			pygame.draw.ellipse(sprite, shade_color(player.color, 0.78), base_inner)
			pygame.draw.ellipse(
				sprite,
				light_color,
				pygame.Rect(base_inner.x + 2, base_inner.y + 1, max(2, base_inner.width // 2), max(2, base_inner.height // 2)),
			)

		body_top = round(piece_cell * 0.29)
		body_bottom = sprite_base_y - round(piece_cell * 0.10)
		body_top_half = max(3, round(piece_cell * 0.14))
		body_bottom_half = max(5, round(piece_cell * 0.29))
		outline_width = max(1, round(piece_cell * 0.035))
		body_outer = (
			(sprite_center_x - body_top_half, body_top),
			(sprite_center_x + body_top_half, body_top),
			(sprite_center_x + body_bottom_half, body_bottom),
			(sprite_center_x - body_bottom_half, body_bottom),
		)
		pygame.draw.polygon(sprite, dark_color, body_outer)
		body_inner = (
			(sprite_center_x - body_top_half + outline_width, body_top + outline_width),
			(sprite_center_x + body_top_half - outline_width, body_top + outline_width),
			(sprite_center_x + body_bottom_half - outline_width, body_bottom - outline_width),
			(sprite_center_x - body_bottom_half + outline_width, body_bottom - outline_width),
		)
		pygame.draw.polygon(sprite, player.color, body_inner)
		mid_top = body_top + outline_width
		mid_bottom = body_bottom - outline_width
		pygame.draw.polygon(
			sprite,
			light_color,
			(body_inner[0], (sprite_center_x, mid_top), (sprite_center_x, mid_bottom), body_inner[3]),
		)
		pygame.draw.polygon(
			sprite,
			shade_color(player.color, 0.70),
			((sprite_center_x, mid_top), body_inner[1], body_inner[2], (sprite_center_x, mid_bottom)),
		)

		head_radius = max(4, round(piece_cell * 0.16))
		head_center_y = round(piece_cell * 0.20)
		pygame.draw.circle(
			sprite,
			dark_color,
			(sprite_center_x + 1, head_center_y + 2),
			head_radius + 1,
		)
		pygame.draw.circle(sprite, light_color, (sprite_center_x - 1, head_center_y - 1), head_radius)
		pygame.draw.circle(
			sprite,
			player.color,
			(sprite_center_x + 1, head_center_y + 1),
			max(2, head_radius - 2),
		)
		highlight_center = (sprite_center_x - max(2, head_radius // 3), head_center_y - max(2, head_radius // 3))
		pygame.draw.circle(sprite, player.pale, highlight_center, max(2, head_radius // 3))
		pygame.draw.circle(
			sprite,
			self.WHITE,
			(highlight_center[0] - 1, highlight_center[1] - 1),
			max(1, head_radius // 7),
		)

		number_size = max(7, round(piece_cell * 0.17))
		number_font = self.fonts.get(number_size)
		if number_font is None:
			number_font = pygame.font.SysFont("DejaVu Sans", number_size, bold=True)
			self.fonts[number_size] = number_font
		number = number_font.render(str(label), True, self.WHITE)
		number_rect = number.get_rect(center=(sprite_center_x, body_bottom - max(1, round(piece_cell * 0.06))))
		sprite.blit(number, number_rect)

		blit_position = (
			ground_point[0] - sprite_center_x,
			round(ground_point[1] - lift) - sprite_base_y,
		)
		self.screen.blit(sprite, blit_position)

	def draw_sidebar(self, rect: pygame.Rect) -> None:
		x, y, width, _ = rect
		self.text("PLAYERS", 13, self.MUTED, (x, y + 8))
		self.player_count_rects.clear()
		button_width = 48
		button_gap = 6
		controls_x = x + width - (button_width * 3 + button_gap * 2)
		for offset, count in enumerate((2, 3, 4)):
			button = pygame.Rect(controls_x + offset * (button_width + button_gap), y + 1, button_width, 30)
			self.player_count_rects[count] = button
			selected = count == self.game.player_count
			pygame.draw.rect(self.screen, self.DARK if selected else self.WHITE, button, border_radius=8)
			pygame.draw.rect(self.screen, self.DARK if selected else self.LINE, button, width=1, border_radius=8)
			color = self.WHITE if selected else self.INK
			self.centered_text(str(count), 15, color, button.center)

		player = self.game.current_player
		turn_card = pygame.Rect(x, y + 48, width, 68)
		pygame.draw.rect(self.screen, player.pale, turn_card, border_radius=12)
		pygame.draw.rect(self.screen, player.color, pygame.Rect(x, y + 48, 5, 68), border_radius=3)
		self.text("ON THE MOVE", 12, self.MUTED, (x + 18, y + 59))
		self.text(player.name.upper(), 23, player.color, (x + 18, y + 77))
		self.text(f"{self.game.turn_cursor + 1} / {len(self.game.active_players)}", 13, self.MUTED, (x + width - 44, y + 77))

		die_y = y + 132
		die_box = pygame.Rect(x, die_y, 88, 88)
		pygame.draw.rect(self.screen, self.WHITE, die_box, border_radius=14)
		pygame.draw.rect(self.screen, self.LINE, die_box, width=1, border_radius=14)
		shown_roll = self.game.die_value or self.game.last_roll
		if shown_roll is None:
			self.centered_text("?", 42, self.MUTED, die_box.center)
		else:
			self.draw_die_face(die_box, shown_roll)

		self.roll_rect = pygame.Rect(x + 104, die_y + 14, width - 104, 60)
		rolling_enabled = self.game.die_value is None and self.game.winner is None
		button_color = player.color if rolling_enabled else (174, 180, 170)
		pygame.draw.rect(self.screen, button_color, self.roll_rect, border_radius=11)
		self.centered_text("ROLL DICE", 16, self.WHITE, (self.roll_rect.centerx, self.roll_rect.y + 23))
		self.centered_text("R", 12, (255, 255, 255, 190), (self.roll_rect.centerx, self.roll_rect.y + 43))

		message_rect = pygame.Rect(x, y + 234, width, 50)
		pygame.draw.rect(self.screen, self.WHITE, message_rect, border_radius=10)
		pygame.draw.rect(self.screen, self.LINE, message_rect, width=1, border_radius=10)
		self.draw_wrapped(self.game.message, 13, self.INK, message_rect.inflate(-16, -8))

		list_y = y + 304
		self.text("RACE STATUS", 13, self.MUTED, (x, list_y))
		row_y = list_y + 25
		for player_index, current in enumerate(PLAYERS):
			row = pygame.Rect(x, row_y + player_index * 48, width, 42)
			active = player_index in self.game.active_players
			is_turn = player_index == self.game.current_player_index and self.game.winner is None
			if active:
				pygame.draw.rect(self.screen, self.WHITE if not is_turn else current.pale, row, border_radius=9)
				if is_turn:
					pygame.draw.rect(self.screen, current.color, pygame.Rect(x, row.y, 4, row.height), border_radius=2)
			else:
				pygame.draw.rect(self.screen, (235, 236, 231), row, border_radius=9)
			pygame.draw.circle(self.screen, current.color if active else (179, 184, 176), (x + 20, row.centery), 6)
			name_color = self.INK if active else self.MUTED
			self.text(current.name, 15, name_color, (x + 36, row.y + 13))
			completed = sum(progress == 57 for progress in self.game.tokens[player_index])
			self.text(f"{completed} / 4 HOME", 12, self.MUTED, (x + width - 80, row.y + 15))

		control_y = row_y + 4 * 48 + 12
		self.new_game_rect = pygame.Rect(x, control_y, width, 45)
		pygame.draw.rect(self.screen, self.DARK, self.new_game_rect, border_radius=10)
		self.centered_text("NEW GAME", 15, self.WHITE, self.new_game_rect.center)
		rule_y = self.new_game_rect.bottom + 13
		rule = "Six to enter  ·  Stars are safe  ·  Exact roll to finish"
		self.draw_wrapped(rule, 12, self.MUTED, pygame.Rect(x, rule_y, width, 38))

	def draw_die_face(self, rect: pygame.Rect, value: int) -> None:
		dots = {
			1: ((0.5, 0.5),),
			2: ((0.28, 0.28), (0.72, 0.72)),
			3: ((0.28, 0.28), (0.5, 0.5), (0.72, 0.72)),
			4: ((0.28, 0.28), (0.72, 0.28), (0.28, 0.72), (0.72, 0.72)),
			5: ((0.28, 0.28), (0.72, 0.28), (0.5, 0.5), (0.28, 0.72), (0.72, 0.72)),
			6: ((0.28, 0.25), (0.72, 0.25), (0.28, 0.5), (0.72, 0.5), (0.28, 0.75), (0.72, 0.75)),
		}
		for dx, dy in dots[value]:
			point = (round(rect.x + rect.width * dx), round(rect.y + rect.height * dy))
			pygame.draw.circle(self.screen, self.INK, point, max(3, rect.width // 18))

	def text(self, value: str, size: int, color: tuple[int, ...], position: tuple[int, int]) -> None:
		font = self.fonts.get(size) or pygame.font.SysFont("DejaVu Sans", size)
		self.screen.blit(font.render(value, True, color[:3]), position)

	def centered_text(self, value: str, size: int, color: tuple[int, ...], position: tuple[int, int]) -> None:
		font = self.fonts.get(size) or pygame.font.SysFont("DejaVu Sans", size)
		self.screen.blit(font.render(value, True, color[:3]), font.render(value, True, color[:3]).get_rect(center=position))

	def draw_wrapped(self, value: str, size: int, color: tuple[int, ...], rect: pygame.Rect) -> None:
		font = self.fonts.get(size) or pygame.font.SysFont("DejaVu Sans", size)
		words = value.split()
		lines: list[str] = []
		line = ""
		for word in words:
			candidate = f"{line} {word}".strip()
			if line and font.size(candidate)[0] > rect.width:
				lines.append(line)
				line = word
			else:
				line = candidate
		if line:
			lines.append(line)
		line_height = font.get_linesize()
		total_height = min(len(lines), max(1, rect.height // line_height)) * line_height
		start_y = rect.y + max(0, (rect.height - total_height) // 2)
		for index, line in enumerate(lines[: max(1, rect.height // line_height)]):
			self.screen.blit(font.render(line, True, color), (rect.x, start_y + index * line_height))


def main() -> None:
	LudoApp().run()


if __name__ == "__main__":
	main()